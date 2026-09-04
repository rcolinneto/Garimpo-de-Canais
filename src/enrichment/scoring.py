"""Score de nicho viral (docs/05-motor-monetizacao-e-score.md).

Três componentes gravados separadamente em `channel_scores` para explicabilidade:
crescimento do canal, monetização detectada e o quanto o nicho inteiro está
bombando. `score_breakdown` guarda os números e pesos usados, para o dashboard
poder responder "por que este canal está em primeiro lugar".
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from src.config.settings import settings
from src.db.models import Channel, ChannelScore, ChannelSnapshot, MonetizationSignal

logger = logging.getLogger(__name__)

# Peso por tipo de sinal: afiliado e loja própria são evidência mais forte de
# monetização do que uma menção solta a patrocínio.
SIGNAL_TYPE_WEIGHTS = {
    "link_afiliado": 1.0,
    "loja_propria": 1.0,
    "infoproduto": 0.8,
    "comunidade_paga": 0.7,
    "link_agregador": 0.6,
    "patrocinio_mencionado": 0.4,
    "elegivel_parceria_plataforma": 0.3,
}


def _size_factor(subscriber_count: int | None) -> float:
    """Penaliza canais já consolidados: o produto procura quem está emergindo."""
    if subscriber_count is None:
        return 1.0
    if subscriber_count > settings.growth_large_channel_subscribers:
        return settings.growth_large_channel_factor
    return 1.0


def calculate_growth_score(
    current: ChannelSnapshot, previous: ChannelSnapshot | None
) -> tuple[float, dict]:
    """Crescimento entre dois snapshots, normalizado para a janela configurada.

    Usa inscritos; cai para views quando o canal oculta a contagem de inscritos.
    Sem histórico anterior não há crescimento a afirmar, então o score é 0.
    """
    if previous is None:
        return 0.0, {"motivo": "sem snapshot anterior para comparar"}

    elapsed_days = (current.collected_at - previous.collected_at).total_seconds() / 86400
    if elapsed_days <= 0:
        return 0.0, {"motivo": "snapshots sem intervalo de tempo entre si"}

    base = "inscritos"
    atual, anterior = current.subscriber_count, previous.subscriber_count
    if atual is None or anterior is None or anterior == 0:
        # Inscritos ocultos: views totais são o melhor proxy disponível.
        base = "views"
        atual, anterior = current.total_view_count, previous.total_view_count
    if atual is None or anterior is None or anterior == 0:
        return 0.0, {"motivo": "métricas insuficientes para calcular crescimento"}

    # Piso no denominador: em bases minúsculas o percentual não significa nada
    # (+2 inscritos em um canal de 17 não é "crescimento de 12%").
    denominador = max(anterior, settings.growth_min_base)
    observed_rate = (atual - anterior) / denominador

    # Normaliza para a janela de referência para que canais com históricos de
    # tamanhos diferentes fiquem comparáveis, com teto na extrapolação.
    normalization_factor = min(
        settings.growth_comparison_days / elapsed_days, settings.growth_max_normalization_factor
    )
    rate = observed_rate * normalization_factor
    size_factor = _size_factor(current.subscriber_count)
    score = max(0.0, min(100.0, rate * 100 * size_factor))

    return score, {
        "base": base,
        "valor_anterior": anterior,
        "valor_atual": atual,
        "denominador_usado": denominador,
        "dias_decorridos": round(elapsed_days, 2),
        "taxa_observada": round(observed_rate, 6),
        "fator_normalizacao": round(normalization_factor, 4),
        "taxa_normalizada": round(rate, 6),
        "janela_referencia_dias": settings.growth_comparison_days,
        "fator_tamanho": size_factor,
    }


def calculate_monetization_score(signals: list[MonetizationSignal]) -> tuple[float, dict]:
    """Soma ponderada dos sinais ativos, pela confiança de cada um."""
    if not signals:
        return 0.0, {"sinais_considerados": 0}

    total = 0.0
    por_tipo: dict[str, float] = {}
    for signal in signals:
        weight = SIGNAL_TYPE_WEIGHTS.get(signal.signal_type, 0.5)
        contribution = float(signal.confidence or 0) * weight
        total += contribution
        por_tipo[signal.signal_type] = round(por_tipo.get(signal.signal_type, 0.0) + contribution, 4)

    score = min(100.0, total * settings.monetization_score_scale)
    return score, {
        "sinais_considerados": len(signals),
        "contribuicao_por_tipo": por_tipo,
        "soma_ponderada": round(total, 4),
        "escala": settings.monetization_score_scale,
        "janela_dias": settings.monetization_window_days,
    }


def calculate_total_score(
    growth_score: float, monetization_score: float, niche_score: float
) -> tuple[float, dict]:
    weights = {
        "crescimento": settings.score_weight_growth,
        "monetizacao": settings.score_weight_monetization,
        "nicho": settings.score_weight_niche,
    }
    total = (
        growth_score * weights["crescimento"]
        + monetization_score * weights["monetizacao"]
        + niche_score * weights["nicho"]
    )
    return round(total, 4), weights


def _latest_and_baseline_snapshots(
    session, channel_id: int
) -> tuple[ChannelSnapshot | None, ChannelSnapshot | None]:
    """Snapshot mais recente e o de referência (~N dias atrás, ou o mais antigo)."""
    latest = (
        session.query(ChannelSnapshot)
        .filter(ChannelSnapshot.channel_id == channel_id)
        .order_by(ChannelSnapshot.collected_at.desc())
        .first()
    )
    if latest is None:
        return None, None

    cutoff = latest.collected_at - timedelta(days=settings.growth_comparison_days)
    baseline = (
        session.query(ChannelSnapshot)
        .filter(
            ChannelSnapshot.channel_id == channel_id,
            ChannelSnapshot.collected_at <= cutoff,
        )
        .order_by(ChannelSnapshot.collected_at.desc())
        .first()
    )
    if baseline is None:
        # Ainda não há N dias de histórico: usa o snapshot mais antigo disponível.
        baseline = (
            session.query(ChannelSnapshot)
            .filter(
                ChannelSnapshot.channel_id == channel_id,
                ChannelSnapshot.id != latest.id,
            )
            .order_by(ChannelSnapshot.collected_at.asc())
            .first()
        )
    return latest, baseline


def _active_signals(session, channel_id: int) -> list[MonetizationSignal]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.monetization_window_days)
    return (
        session.query(MonetizationSignal)
        .filter(
            MonetizationSignal.channel_id == channel_id,
            MonetizationSignal.detected_at >= cutoff,
        )
        .all()
    )


def run_enrichment(session) -> int:
    """Calcula e grava um score por canal ativo. Devolve quantos canais pontuaram.

    Roda em duas passadas de propósito: o score de nicho é a média do crescimento
    dos canais daquele nicho, então todos os `growth_score` precisam existir antes
    de qualquer `total_score` ser fechado.
    """
    channels = session.query(Channel).filter(Channel.status == "active").all()
    if not channels:
        return 0

    parciais = []
    for channel in channels:
        latest, baseline = _latest_and_baseline_snapshots(session, channel.id)
        if latest is None:
            continue
        growth_score, growth_detail = calculate_growth_score(latest, baseline)
        monetization_score, monetization_detail = calculate_monetization_score(
            _active_signals(session, channel.id)
        )
        parciais.append(
            {
                "channel": channel,
                "growth_score": growth_score,
                "growth_detail": growth_detail,
                "monetization_score": monetization_score,
                "monetization_detail": monetization_detail,
            }
        )

    # Nicho bombando = vários canais crescendo ao mesmo tempo, não um canal sortudo.
    por_nicho: dict[int, list[float]] = {}
    for item in parciais:
        niche_id = item["channel"].niche_id
        if niche_id is not None:
            por_nicho.setdefault(niche_id, []).append(item["growth_score"])
    media_por_nicho = {
        niche_id: sum(scores) / len(scores) for niche_id, scores in por_nicho.items()
    }

    calculated_at = datetime.now(timezone.utc)
    for item in parciais:
        niche_id = item["channel"].niche_id
        niche_score = media_por_nicho.get(niche_id, 0.0) if niche_id is not None else 0.0
        total_score, weights = calculate_total_score(
            item["growth_score"], item["monetization_score"], niche_score
        )
        session.add(
            ChannelScore(
                channel_id=item["channel"].id,
                calculated_at=calculated_at,
                growth_score=item["growth_score"],
                monetization_score=item["monetization_score"],
                niche_virality_score=niche_score,
                total_score=total_score,
                score_breakdown={
                    "pesos": weights,
                    "crescimento": item["growth_detail"],
                    "monetizacao": item["monetization_detail"],
                    "nicho": {
                        "niche_id": niche_id,
                        "canais_no_nicho": len(por_nicho.get(niche_id, [])) if niche_id else 0,
                        "observacao": None
                        if niche_id
                        else "canal sem nicho configurado — componente de nicho não se aplica",
                    },
                },
            )
        )

    logger.info("Enriquecimento: %d canais pontuados", len(parciais))
    return len(parciais)

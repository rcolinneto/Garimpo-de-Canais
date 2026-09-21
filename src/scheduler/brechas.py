"""Mapeamento e validação de brechas (Fase 9).

Passos MAPEAR e VALIDAR da metodologia: dado um formato que já provou demanda
(um vídeo outlier), existe mercado onde ele ainda não tem dono?

Respeita a estratégia de custo de `docs/04`: a chamada cara (`search.list`,
100 unidades) só entra para **confirmar** uma candidata que já passou pelo
funil, e um mercado por ciclo, em rodízio (`docs/00b`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from src.config.settings import settings
from src.db.models import Market, Opportunity, TitleSignal, Video, VideoOutlier
from src.enrichment.opportunities import (
    SinaisDeMercado,
    calcular_opportunity_score,
    espaco_livre,
)

logger = logging.getLogger(__name__)

# Carteira inicial decidida em docs/00b: um mercado de CPM alto e três de menor
# concorrência, para comparar na prática antes de concentrar esforço. Os RPMs
# são ESTIMATIVA DE MERCADO, não dado da API — precisam de revisão periódica.
CARTEIRA_INICIAL = [
    {
        "region_code": "US",
        "language_code": "en",
        "name": "Estados Unidos (inglês)",
        "rpm_estimado": 12.0,
        "falantes_estimados": 400_000_000,
    },
    {
        "region_code": "DE",
        "language_code": "de",
        "name": "Alemanha (alemão)",
        "rpm_estimado": 9.0,
        "falantes_estimados": 95_000_000,
    },
    {
        "region_code": "IT",
        "language_code": "it",
        "name": "Itália (italiano)",
        "rpm_estimado": 5.0,
        "falantes_estimados": 65_000_000,
    },
    {
        "region_code": "PL",
        "language_code": "pl",
        "name": "Polônia (polonês)",
        "rpm_estimado": 6.0,
        "falantes_estimados": 40_000_000,
    },
]


def semear_mercados(session) -> int:
    """Cadastra a carteira inicial, sem duplicar o que já existe."""
    existentes = {
        codigo for (codigo,) in session.execute(select(Market.region_code)).all()
    }
    novos = 0
    for dados in CARTEIRA_INICIAL:
        if dados["region_code"] in existentes:
            continue
        session.add(Market(**dados))
        novos += 1
    session.flush()
    return novos


def _mercados_do_ciclo(session) -> list[Market]:
    """Mercados da vez, no rodízio: o menos recentemente validado primeiro."""
    return list(
        session.execute(
            select(Market)
            .where(Market.active.is_(True))
            .order_by(Market.last_validated_at.asc().nullsfirst(), Market.id)
            .limit(settings.markets_per_run)
        ).scalars()
    )


def _candidatos(session, limite: int) -> list[tuple[Video, float]]:
    """Vídeos com maior outlier — os formatos que já provaram demanda.

    É a condição 1 da metodologia ("o assunto já performa"). Sem outlier não há
    brecha: seria apostar, não ler dado.
    """
    ultimos = (
        select(VideoOutlier.video_id, VideoOutlier.outlier_score)
        .distinct(VideoOutlier.video_id)
        .order_by(VideoOutlier.video_id, VideoOutlier.calculated_at.desc())
        .subquery("ultimo")
    )
    consulta = (
        select(Video, ultimos.c.outlier_score)
        .join(ultimos, ultimos.c.video_id == Video.id)
        .where(ultimos.c.outlier_score >= settings.outlier_minimo_para_brecha)
    )
    if settings.exigir_formato_reconhecivel:
        # Brecha pressupõe um FORMATO a portar (condição 2: "existe um ângulo
        # vago"). Um vídeo sem peça reconhecível no título não tem ângulo para
        # levar a outro mercado. Medido nos dados reais: sem este filtro o topo
        # da lista era letra de música e coletânea — conteúdo que performa, mas
        # não se replica. E como o chefe decide direto, sem curadoria prévia
        # (docs/00b), lixo no topo custa a confiança na tela inteira.
        consulta = consulta.where(
            select(TitleSignal.id)
            .where(TitleSignal.video_id == Video.id)
            .exists()
        )
    linhas = session.execute(
        consulta.order_by(ultimos.c.outlier_score.desc()).limit(limite)
    ).all()
    return [(video, float(score or 0)) for video, score in linhas]


def _termo_de_busca(video: Video) -> str:
    """Termo usado para checar se alguém já ocupa o assunto naquele idioma.

    Usa as primeiras palavras do título, sem números nem pontuação: o que se
    procura é o ASSUNTO, não o título exato — procurar o título exato só
    acharia cópias dele, que é justamente o que a metodologia diz não fazer.
    """
    palavras = [
        palavra.strip(".,:;!?()[]\"'—-")
        for palavra in (video.title or "").split()
        if not palavra.strip(".,:;!?()[]\"'—-").isdigit()
    ]
    return " ".join(p for p in palavras if p)[:80]


def mapear_brechas(session, collector, agora: datetime | None = None) -> dict:
    """Cria/atualiza brechas para os mercados da vez. Devolve o resumo."""
    agora = agora or datetime.now(timezone.utc)
    semear_mercados(session)

    mercados = _mercados_do_ciclo(session)
    if not mercados:
        return {"mercados": 0, "brechas": 0, "motivo": "nenhum mercado ativo"}

    candidatos = _candidatos(session, settings.opportunities_per_run)
    if not candidatos:
        return {"mercados": len(mercados), "brechas": 0, "motivo": "nenhum outlier elegível"}

    criadas = 0
    for mercado in mercados:
        for video, outlier_score in candidatos:
            ja_existe = session.execute(
                select(Opportunity.id).where(
                    Opportunity.video_id == video.id,
                    Opportunity.market_id == mercado.id,
                )
            ).first()
            if ja_existe:
                continue

            termo = _termo_de_busca(video)
            evidencia = collector.avaliar_espaco_no_mercado(
                termo, mercado.region_code, mercado.language_code
            )
            nota_espaco, detalhe_espaco = espaco_livre(
                evidencia["resultados"], evidencia["antigos"], evidencia["canais_pequenos"]
            )
            resultado = calcular_opportunity_score(
                outlier_score,
                # float() na fronteira: colunas Numeric voltam como Decimal, que
                # não opera com float — e a lógica de score é toda em float.
                SinaisDeMercado(
                    float(mercado.rpm_estimado) if mercado.rpm_estimado is not None else None,
                    mercado.falantes_estimados,
                ),
                nota_espaco,
                detalhe_espaco,
            )
            session.add(
                Opportunity(
                    video_id=video.id,
                    market_id=mercado.id,
                    status="mapeada",
                    volume_evidence={"termo": termo, "resultados": evidencia["resultados"]},
                    concorrencia_evidence={**evidencia, **resultado["breakdown"]},
                    opportunity_score=resultado["opportunity_score"],
                )
            )
            criadas += 1

        mercado.last_validated_at = agora

    session.flush()
    logger.info(
        "Brechas mapeadas: %d em %d mercado(s)", criadas, len(mercados)
    )
    return {"mercados": len(mercados), "brechas": criadas}

"""Detecção de vídeos "outlier" — passo GARIMPAR da metodologia Brecha Viral.

Um vídeo outlier performa muito acima da média **do próprio canal**. A
comparação é sempre interna: 270 mil views é pouco para um canal que faz 800
mil e é um evento para um que faz 20 mil. Comparar canais entre si não diria
nada sobre o que fez aquele vídeo específico funcionar.

Especificação em `docs/05-motor-monetizacao-e-score.md`, seção "Outlier score".
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone

from src.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoParaOutlier:
    """O que o cálculo precisa saber de um vídeo — sem acoplar ao ORM."""

    youtube_video_id: str
    view_count: int | None
    published_at: datetime | None
    duration_seconds: int | None


def e_short(duration_seconds: int | None) -> bool | None:
    """Short, vídeo longo, ou desconhecido (None).

    Desconhecido é um estado real, não um erro: os vídeos recuperados do
    histórico de `raw_payload` não têm duração, porque a coleta antiga não
    pedia `contentDetails` à API.
    """
    if duration_seconds is None:
        return None
    return duration_seconds <= settings.short_max_duration_seconds


def calcular_baseline(
    videos: list[VideoParaOutlier], alvo: VideoParaOutlier
) -> tuple[float | None, dict]:
    """Média de views dos *outros* vídeos da mesma classe de duração.

    Dois cuidados que mudam o resultado:

    1. **O próprio vídeo é excluído da média.** Senão um vídeo que explodiu
       infla justamente a média que deveria julgá-lo, e quanto maior o pico,
       mais ele se esconde.
    2. **Short só compara com Short.** As distribuições de views não são
       comparáveis; misturar as duas produz outlier fantasma. Quando a duração
       é desconhecida, comparamos com todos e registramos isso no breakdown —
       é melhor um número honesto e marcado do que nenhum número.
    """
    classe_alvo = e_short(alvo.duration_seconds)
    comparaveis = [
        video
        for video in videos
        if video.youtube_video_id != alvo.youtube_video_id
        and video.view_count is not None
        and (classe_alvo is None or e_short(video.duration_seconds) in (classe_alvo, None))
    ]
    if not comparaveis:
        return None, {"motivo": "sem outros vídeos do canal para comparar"}

    baseline = sum(video.view_count for video in comparaveis) / len(comparaveis)
    return baseline, {
        "videos_comparados": len(comparaveis),
        "classe": {True: "short", False: "longo", None: "duração desconhecida"}[classe_alvo],
        "duracao_conhecida": classe_alvo is not None,
    }


def peso_de_recencia(published_at: datetime | None, agora: datetime | None = None) -> float:
    """Decai com a idade do vídeo, entre 1.0 (hoje) e um piso configurável.

    A metodologia é explícita que recência é sinal — "quanto mais recente e mais
    views, melhor". Um pico de 3 dias atrás é oportunidade; o mesmo pico de 8
    meses atrás é história, e ocupar aquele espaço já não chega primeiro.
    """
    if published_at is None:
        return settings.outlier_recency_floor

    agora = agora or datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    dias = max(0.0, (agora - published_at).total_seconds() / 86400)
    meia_vida = settings.outlier_recency_halflife_days
    peso = 0.5 ** (dias / meia_vida)
    return max(settings.outlier_recency_floor, min(1.0, peso))


def calcular_outlier(
    alvo: VideoParaOutlier,
    videos_do_canal: list[VideoParaOutlier],
    agora: datetime | None = None,
) -> dict | None:
    """Calcula o outlier de um vídeo. Devolve None quando não há como afirmar.

    Devolver None em vez de zero é deliberado: "não dá para comparar" e "está
    na média" são coisas diferentes, e gravar zero apagaria essa diferença.
    """
    if alvo.view_count is None:
        return None

    baseline, detalhe_baseline = calcular_baseline(videos_do_canal, alvo)
    if not baseline or baseline <= 0:
        return None

    # Piso no denominador: num canal que faz 380 views, um vídeo de 4 mil vira
    # "11x a média" sem provar nada sobre o formato. Mesmo raciocínio do
    # growth_min_base no score de crescimento.
    denominador = max(baseline, settings.outlier_min_baseline_views)
    ratio = alvo.view_count / denominador
    peso = peso_de_recencia(alvo.published_at, agora)

    # Escala logarítmica: 1000x a média é mais que 11x, mas não cem vezes mais
    # interessante. Numa escala linear com saturação, os dois empatariam no teto
    # e só a recência os separaria.
    if ratio <= 1.0:
        bruto = 0.0
    else:
        bruto = min(100.0, math.log10(ratio) / math.log10(settings.outlier_ratio_teto) * 100)
    score = bruto * peso

    return {
        "baseline_views": baseline,
        "outlier_ratio": ratio,
        "recency_weight": peso,
        "outlier_score": score,
        "breakdown": {
            "views": alvo.view_count,
            "baseline": detalhe_baseline,
            "denominador_usado": denominador,
            "piso_aplicado": denominador > baseline,
            "ratio_teto": settings.outlier_ratio_teto,
            "score_antes_da_recencia": bruto,
            "publicado_em": alvo.published_at.isoformat() if alvo.published_at else None,
        },
    }

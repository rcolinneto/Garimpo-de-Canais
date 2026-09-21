"""Persistência de vídeos e cálculo de outliers (Fase 7).

Os vídeos já vinham sendo coletados desde a Fase 2 — ficavam dentro de
`channel_snapshots.raw_payload`. Este módulo os promove a tabela própria, o que
permite acompanhar cada vídeo ao longo do tempo e calcular o outlier.

Consequência prática: o histórico já coletado **não se perde e não custa cota
nova** para ser aproveitado — `backfill_videos_do_historico` o reconstrói a
partir do payload que já está no banco.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from src.db.models import TitleSignal, Video, VideoOutlier, VideoSnapshot
from src.enrichment.outliers import VideoParaOutlier, calcular_outlier
from src.enrichment.title_anatomy import detect_title_signals

logger = logging.getLogger(__name__)

_DURACAO_ISO = re.compile(
    r"^P(?:(?P<dias>\d+)D)?T(?:(?P<horas>\d+)H)?(?:(?P<min>\d+)M)?(?:(?P<seg>\d+)S)?$"
)


def duracao_em_segundos(duracao_iso: str | None) -> int | None:
    """Converte a duração ISO-8601 da API ("PT1M30S") para segundos."""
    if not duracao_iso:
        return None
    match = _DURACAO_ISO.match(duracao_iso)
    if not match:
        return None
    partes = {chave: int(valor or 0) for chave, valor in match.groupdict().items()}
    return partes["dias"] * 86400 + partes["horas"] * 3600 + partes["min"] * 60 + partes["seg"]


def _para_int(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _data(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def extrair_videos(raw_payload: dict | None) -> list[dict]:
    """Normaliza os itens de vídeo do payload bruto da API."""
    if not raw_payload:
        return []
    extraidos = []
    for item in raw_payload.get("recent_videos", []):
        youtube_video_id = item.get("id")
        if not youtube_video_id:
            continue
        snippet = item.get("snippet", {})
        estatisticas = item.get("statistics", {})
        extraidos.append(
            {
                "youtube_video_id": youtube_video_id,
                "title": snippet.get("title"),
                "published_at": _data(snippet.get("publishedAt")),
                # Ausente nos payloads antigos: só passamos a pedir contentDetails
                # na Fase 7. Fica nulo, e o cálculo trata isso explicitamente.
                "duration_seconds": duracao_em_segundos(
                    item.get("contentDetails", {}).get("duration")
                ),
                "view_count": _para_int(estatisticas.get("viewCount")),
                "like_count": _para_int(estatisticas.get("likeCount")),
                "comment_count": _para_int(estatisticas.get("commentCount")),
            }
        )
    return extraidos


def persistir_videos(
    session, channel_id: int, raw_payload: dict | None, collected_at: datetime | None = None
) -> list[Video]:
    """Grava/atualiza os vídeos do canal e um snapshot de métricas de cada um."""
    dados = extrair_videos(raw_payload)
    if not dados:
        return []

    collected_at = collected_at or datetime.now(timezone.utc)
    ids = [item["youtube_video_id"] for item in dados]
    existentes = {
        video.youtube_video_id: video
        for video in session.execute(
            select(Video).where(Video.youtube_video_id.in_(ids))
        ).scalars()
    }

    videos = []
    for item in dados:
        video = existentes.get(item["youtube_video_id"])
        if video is None:
            video = Video(
                channel_id=channel_id,
                youtube_video_id=item["youtube_video_id"],
                title=item["title"],
                published_at=item["published_at"],
                duration_seconds=item["duration_seconds"],
            )
            session.add(video)
            session.flush()
            existentes[video.youtube_video_id] = video
        else:
            # Título pode ser editado pelo dono do canal, e a duração só aparece
            # depois que o payload passou a trazer contentDetails: completar sem
            # apagar o que já se sabia.
            video.title = item["title"] or video.title
            video.duration_seconds = item["duration_seconds"] or video.duration_seconds
            video.published_at = video.published_at or item["published_at"]

        session.add(
            VideoSnapshot(
                video_id=video.id,
                collected_at=collected_at,
                view_count=item["view_count"],
                like_count=item["like_count"],
                comment_count=item["comment_count"],
            )
        )
        _persistir_sinais_de_titulo(session, video)
        videos.append(video)

    return videos


def _persistir_sinais_de_titulo(session, video: Video) -> None:
    """Grava as peças do título ainda não registradas para este vídeo.

    Sem duplicar: o título raramente muda, e o snapshot roda todo dia — sem
    esta checagem o mesmo sinal viraria uma linha nova por dia.
    """
    if not video.title:
        return
    ja_gravados = {
        tipo
        for (tipo,) in session.execute(
            select(TitleSignal.signal_type).where(TitleSignal.video_id == video.id)
        ).all()
    }
    for sinal in detect_title_signals(video.title):
        if sinal.signal_type in ja_gravados:
            continue
        session.add(
            TitleSignal(
                video_id=video.id,
                signal_type=sinal.signal_type,
                evidence=sinal.evidence,
                confidence=sinal.confidence,
            )
        )


def _ultimas_views(session, video_ids: list[int]) -> dict[int, int | None]:
    """Views mais recentes de cada vídeo (DISTINCT ON, específico do Postgres)."""
    if not video_ids:
        return {}
    linhas = session.execute(
        select(VideoSnapshot.video_id, VideoSnapshot.view_count)
        .where(VideoSnapshot.video_id.in_(video_ids))
        .distinct(VideoSnapshot.video_id)
        .order_by(VideoSnapshot.video_id, VideoSnapshot.collected_at.desc())
    ).all()
    return {video_id: views for video_id, views in linhas}


def calcular_outliers_do_canal(session, channel_id: int, agora: datetime | None = None) -> int:
    """Calcula e grava o outlier de cada vídeo do canal. Devolve quantos gravou."""
    videos = list(
        session.execute(select(Video).where(Video.channel_id == channel_id)).scalars()
    )
    if len(videos) < 2:
        # Com um vídeo só não existe "média do canal" contra a qual comparar.
        return 0

    views = _ultimas_views(session, [video.id for video in videos])
    universo = [
        VideoParaOutlier(
            youtube_video_id=video.youtube_video_id,
            view_count=views.get(video.id),
            published_at=video.published_at,
            duration_seconds=video.duration_seconds,
        )
        for video in videos
    ]

    gravados = 0
    for video, alvo in zip(videos, universo):
        resultado = calcular_outlier(alvo, universo, agora)
        if resultado is None:
            continue
        session.add(VideoOutlier(video_id=video.id, **resultado))
        gravados += 1
    return gravados


def backfill_videos_do_historico(session, limite_de_canais: int | None = None) -> dict:
    """Reconstrói os vídeos a partir dos snapshots de canal já guardados.

    Zero unidades de cota: tudo já está em `channel_snapshots.raw_payload`. Roda
    uma vez após a migration da Fase 7 para a camada de oportunidade nascer com
    o histórico que o sistema vinha acumulando desde a Fase 2.
    """
    from src.db.models import Channel, ChannelSnapshot

    consulta = select(Channel.id).order_by(Channel.id)
    if limite_de_canais:
        consulta = consulta.limit(limite_de_canais)
    channel_ids = list(session.execute(consulta).scalars())

    canais_tocados = 0
    outliers = 0
    for channel_id in channel_ids:
        snapshots = list(
            session.execute(
                select(ChannelSnapshot)
                .where(ChannelSnapshot.channel_id == channel_id)
                .order_by(ChannelSnapshot.collected_at)
            ).scalars()
        )
        if not snapshots:
            continue
        for snapshot in snapshots:
            persistir_videos(session, channel_id, snapshot.raw_payload, snapshot.collected_at)
        session.flush()
        outliers += calcular_outliers_do_canal(session, channel_id)
        canais_tocados += 1
        session.commit()

    logger.info(
        "Backfill de vídeos concluído: %d canais, %d outliers calculados",
        canais_tocados,
        outliers,
    )
    return {"canais": canais_tocados, "outliers": outliers}

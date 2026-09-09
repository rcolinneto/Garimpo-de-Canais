"""Lógica de descoberta compartilhada entre o job agendado e a busca sob
demanda do dashboard (Tela 2) — as duas usam exatamente as mesmas regras de
cadastro e filtro de relevância, só mudam o gatilho.
"""

import logging
from datetime import datetime, timezone

from src.collectors.youtube import QuotaExceededError, YouTubeCollector, is_relevant_candidate
from src.db.models import Channel, ChannelSnapshot, Niche

logger = logging.getLogger(__name__)


def snapshot_row(channel_id: int, snapshot) -> ChannelSnapshot:
    payload = dict(snapshot.raw_payload)
    payload["max_recent_video_views"] = snapshot.max_recent_video_views
    return ChannelSnapshot(
        channel_id=channel_id,
        collected_at=snapshot.collected_at,
        subscriber_count=snapshot.subscriber_count,
        total_view_count=snapshot.total_view_count,
        video_count=snapshot.video_count,
        avg_views_last_n_videos=snapshot.avg_views_last_n_videos,
        engagement_rate=snapshot.engagement_rate,
        raw_payload=payload,
    )


def register_candidates(
    session, collector: YouTubeCollector, refs, niche_id: int | None
) -> tuple[list[Channel], bool]:
    """Cadastra os candidatos que passarem no filtro de relevância.

    Devolve (canais registrados nesta chamada, se a cota estourou no meio da
    lista). Importante: se a cota acabar checando o 5º de 30 candidatos, os 4
    já registrados **não são descartados** — ficam na sessão (flush já rodou)
    e voltam na lista, para quem chamou saber exatamente o que já tem antes de
    decidir parar. A exceção de cota não propaga daqui: o próximo lugar que
    chamar a API (próximo nicho, por exemplo) já vai estourar de novo sozinho,
    então não há necessidade de silenciar informação aqui para sinalizar isso.
    """
    registrados: list[Channel] = []
    for ref in refs:
        already_known = (
            session.query(Channel).filter_by(youtube_channel_id=ref.youtube_channel_id).first()
        )
        if already_known:
            continue

        try:
            snapshot = collector.fetch_snapshot(ref)
        except QuotaExceededError:
            logger.warning(
                "Cota esgotada registrando candidatos; %d já registrados até aqui",
                len(registrados),
            )
            return registrados, True
        if snapshot is None or not is_relevant_candidate(snapshot):
            continue

        channel = Channel(
            youtube_channel_id=ref.youtube_channel_id,
            handle=snapshot.channel_ref.handle,
            display_name=snapshot.channel_ref.display_name or ref.display_name,
            url=snapshot.channel_ref.url or ref.url,
            niche_id=niche_id,
            first_seen_subscriber_count=snapshot.subscriber_count,
            status="active",
        )
        session.add(channel)
        session.flush()
        session.add(snapshot_row(channel.id, snapshot))
        registrados.append(channel)
        logger.info("Canal descoberto: %s (%s)", channel.display_name, channel.youtube_channel_id)
    return registrados, False


def discover_niche_now(
    session, collector: YouTubeCollector, niche: Niche
) -> tuple[list[Channel], bool]:
    """Descobre candidatos para um único nicho (search.list, 100 unidades) e
    os cadastra. Usada tanto pelo rodízio diário quanto pela busca sob demanda.

    Devolve (canais registrados, se a cota estourou no meio do processo).
    """
    refs = collector.discover_candidates(list(niche.keywords or []))
    registrados, cota_esgotada = register_candidates(session, collector, refs, niche.id)
    niche.last_discovery_at = datetime.now(timezone.utc)
    return registrados, cota_esgotada

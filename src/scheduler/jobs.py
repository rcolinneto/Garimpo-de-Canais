"""Jobs de coleta agendados via APScheduler.

Uso manual:  python -m src.scheduler.jobs discovery
             python -m src.scheduler.jobs snapshot
Agendado:    python -m src.scheduler.jobs start

Toda execução vira uma linha em `collection_runs`, incluindo as unidades de cota
gastas — é essa tabela que responde "a coleta rodou hoje?" (docs/07).
"""

import logging
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select

from src.collectors.models import ChannelRef
from src.collectors.youtube import QuotaExceededError, YouTubeCollector, is_relevant_candidate
from src.config.logging import configure_logging
from src.config.settings import settings
from src.db.models import Channel, ChannelSnapshot, CollectionRun, Niche
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _persist_run(
    job_type: str,
    started_at: datetime,
    status: str,
    items_processed: int,
    api_units_consumed: int,
    error_message: str | None = None,
) -> None:
    """Grava o resultado da execução em sessão própria.

    Sessão separada de propósito: se o job morreu com a transação suja, o log da
    execução ainda precisa ser gravado.
    """
    with SessionLocal() as session:
        session.add(
            CollectionRun(
                job_type=job_type,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                status=status,
                items_processed=items_processed,
                error_message=error_message,
                api_units_consumed=api_units_consumed,
            )
        )
        session.commit()


def _snapshot_row(channel_id: int, snapshot) -> ChannelSnapshot:
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


def _register_candidates(session, collector: YouTubeCollector, refs, niche_id: int | None) -> int:
    """Cadastra os candidatos que passarem no filtro de relevância. Devolve quantos entraram."""
    registered = 0
    for ref in refs:
        already_known = (
            session.query(Channel).filter_by(youtube_channel_id=ref.youtube_channel_id).first()
        )
        if already_known:
            continue

        snapshot = collector.fetch_snapshot(ref)
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
        session.add(_snapshot_row(channel.id, snapshot))
        registered += 1
        logger.info("Canal descoberto: %s (%s)", channel.display_name, channel.youtube_channel_id)
    return registered


def run_discovery_job() -> None:
    """Descobre canais novos: rodízio de nichos via search.list + vídeos em alta."""
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message = None
    processed = 0
    # Construído dentro do try: sem chave configurada isso levanta, e a falha
    # precisa aparecer em `collection_runs` como qualquer outra.
    collector = None

    try:
        collector = YouTubeCollector(quota_budget=settings.discovery_quota_budget)
        with SessionLocal() as session:
            niches = (
                session.query(Niche)
                .filter_by(active=True)
                .order_by(Niche.last_discovery_at.asc().nulls_first())
                .limit(settings.discovery_niches_per_run)
                .all()
            )
            for niche in niches:
                refs = collector.discover_candidates(list(niche.keywords or []))
                processed += _register_candidates(session, collector, refs, niche.id)
                niche.last_discovery_at = datetime.now(timezone.utc)
                # Commit por nicho: se a cota acabar no meio, o que já foi descoberto fica.
                session.commit()

            trending_refs = collector.discover_trending_candidates()
            processed += _register_candidates(session, collector, trending_refs, None)
            session.commit()
    except QuotaExceededError as error:
        status = "partial"
        error_message = str(error)
        logger.warning("Descoberta interrompida por cota: %s", error)
    except Exception as error:  # noqa: BLE001 - o job registra e segue vivo para amanhã
        status = "failed"
        error_message = str(error)
        logger.exception("Falha no job de descoberta")
    finally:
        units = collector.units_consumed if collector else 0
        _persist_run("discovery", started_at, status, processed, units, error_message)

    logger.info(
        "Descoberta finalizada (%s): %d canais novos, %d unidades de cota",
        status,
        processed,
        units,
    )


def _channels_due_for_snapshot(session) -> list[Channel]:
    """Canais ativos, do snapshot mais antigo para o mais recente.

    Essa ordem é o que faz o job "retomar de onde parou": quem já foi coletado hoje
    vai para o fim da fila na execução seguinte.
    """
    last_snapshot = (
        select(
            ChannelSnapshot.channel_id.label("channel_id"),
            func.max(ChannelSnapshot.collected_at).label("last_collected_at"),
        )
        .group_by(ChannelSnapshot.channel_id)
        .subquery()
    )
    return (
        session.query(Channel)
        .outerjoin(last_snapshot, Channel.id == last_snapshot.c.channel_id)
        .filter(Channel.status == "active")
        .order_by(last_snapshot.c.last_collected_at.asc().nulls_first())
        .all()
    )


def run_snapshot_job() -> None:
    """Atualiza as métricas de todos os canais já cadastrados (channels.list, barato)."""
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message = None
    processed = 0
    collector = None

    try:
        collector = YouTubeCollector(quota_budget=settings.snapshot_quota_budget)
        with SessionLocal() as session:
            for channel in _channels_due_for_snapshot(session):
                ref = ChannelRef(
                    youtube_channel_id=channel.youtube_channel_id,
                    handle=channel.handle,
                    display_name=channel.display_name,
                    url=channel.url,
                )
                snapshot = collector.fetch_snapshot(ref)
                if snapshot is None:
                    # Canal saiu do ar: marca como removido e preserva o histórico.
                    channel.status = "removed"
                    logger.info("Canal removido do YouTube: %s", channel.youtube_channel_id)
                else:
                    session.add(_snapshot_row(channel.id, snapshot))
                    channel.display_name = snapshot.channel_ref.display_name or channel.display_name
                    channel.handle = snapshot.channel_ref.handle or channel.handle
                session.commit()
                processed += 1
    except QuotaExceededError as error:
        status = "partial"
        error_message = str(error)
        logger.warning("Snapshot interrompido por cota após %d canais: %s", processed, error)
    except Exception as error:  # noqa: BLE001
        status = "failed"
        error_message = str(error)
        logger.exception("Falha no job de snapshot")
    finally:
        units = collector.units_consumed if collector else 0
        _persist_run("snapshot", started_at, status, processed, units, error_message)

    logger.info(
        "Snapshot finalizado (%s): %d canais, %d unidades de cota",
        status,
        processed,
        units,
    )


def _add_jobs(scheduler) -> None:
    scheduler.add_job(
        run_discovery_job,
        CronTrigger.from_crontab(settings.discovery_cron),
        id="discovery",
        replace_existing=True,
    )
    scheduler.add_job(
        run_snapshot_job,
        CronTrigger.from_crontab(settings.snapshot_cron),
        id="snapshot",
        replace_existing=True,
    )


def build_background_scheduler() -> BackgroundScheduler:
    """Scheduler para rodar dentro do processo da API (docs/07)."""
    scheduler = BackgroundScheduler()
    _add_jobs(scheduler)
    return scheduler


def start_scheduler() -> None:
    """Roda os jobs em primeiro plano (processo dedicado)."""
    scheduler = BlockingScheduler()
    _add_jobs(scheduler)
    logger.info(
        "Scheduler iniciado — descoberta: '%s', snapshot: '%s'",
        settings.discovery_cron,
        settings.snapshot_cron,
    )
    scheduler.start()


COMMANDS = {
    "discovery": run_discovery_job,
    "snapshot": run_snapshot_job,
    "start": start_scheduler,
}


if __name__ == "__main__":
    configure_logging()
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    if command not in COMMANDS:
        print(f"Uso: python -m src.scheduler.jobs [{'|'.join(COMMANDS)}]")
        raise SystemExit(1)
    COMMANDS[command]()

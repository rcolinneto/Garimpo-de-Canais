"""Jobs de coleta agendados via APScheduler.

Uso manual:  python -m src.scheduler.jobs discovery
             python -m src.scheduler.jobs snapshot
Agendado:    python -m src.scheduler.jobs start

Toda execução vira uma linha em `collection_runs`, incluindo as unidades de cota
gastas — é essa tabela que responde "a coleta rodou hoje?" (docs/07).
"""

import logging
import sys
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select

from src.collectors.models import ChannelRef
from src.collectors.youtube import QuotaExceededError, YouTubeCollector
from src.config.logging import configure_logging
from src.config.settings import settings
from src.db.models import Channel, ChannelSnapshot, CollectionRun, MonetizationSignal, Niche
from src.db.session import SessionLocal
from src.enrichment.monetization import dedupe_key, detect_signals
from src.enrichment.scoring import run_enrichment
from src.scheduler.alerts import alertar_falha_de_job, run_alerts_job
from src.scheduler.discovery import discover_niche_now, register_candidates, snapshot_row

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

    # docs/09: falha de job avisa por e-mail, para não se descobrir dias depois
    # que o dashboard está desatualizado. `partial` não entra aqui porque parar
    # por cota é comportamento previsto, não falha.
    if status == "failed":
        alertar_falha_de_job(job_type, error_message)


def _persist_monetization_signals(
    session, channel_id: int, ref: ChannelRef, collector: YouTubeCollector, snapshot
) -> int:
    """Detecta e grava sinais de monetização novos para o canal.

    Um sinal já detectado recentemente não é regravado: a tabela existe para mostrar
    *quando* o canal passou a monetizar, e uma linha por dia para o mesmo link só
    esconderia essa informação.
    """
    content_signals = collector.fetch_recent_content_signals(ref)
    detected = detect_signals(content_signals, snapshot)
    if not detected:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.monetization_signal_dedupe_days)
    recentes = {
        dedupe_key(signal.signal_type, signal.evidence or "")
        for signal in session.query(MonetizationSignal)
        .filter(
            MonetizationSignal.channel_id == channel_id,
            MonetizationSignal.detected_at >= cutoff,
        )
        .all()
    }

    novos = 0
    for signal in detected:
        if dedupe_key(signal.signal_type, signal.evidence) in recentes:
            continue
        session.add(
            MonetizationSignal(
                channel_id=channel_id,
                signal_type=signal.signal_type,
                evidence=signal.evidence,
                confidence=signal.confidence,
            )
        )
        novos += 1
    return novos


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
                novos, cota_esgotada = discover_niche_now(session, collector, niche)
                processed += len(novos)
                # Commit por nicho: se a cota acabar no meio, o que já foi descoberto fica.
                session.commit()
                if cota_esgotada:
                    raise QuotaExceededError(f"Cota esgotada durante o nicho '{niche.name}'")

            trending_refs = collector.discover_trending_candidates()
            trending_novos, _ = register_candidates(session, collector, trending_refs, None)
            processed += len(trending_novos)
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
                try:
                    snapshot = collector.fetch_snapshot(ref)
                    if snapshot is None:
                        # Canal saiu do ar: marca como removido e preserva o histórico.
                        channel.status = "removed"
                        logger.info("Canal removido do YouTube: %s", channel.youtube_channel_id)
                    else:
                        session.add(snapshot_row(channel.id, snapshot))
                        channel.display_name = (
                            snapshot.channel_ref.display_name or channel.display_name
                        )
                        channel.handle = snapshot.channel_ref.handle or channel.handle
                        # Os textos recentes já estão em cache do snapshot: 0 unidades.
                        _persist_monetization_signals(session, channel.id, ref, collector, snapshot)
                except QuotaExceededError as error:
                    # Interrompe a coleta, mas ainda enriquece o que já foi coletado.
                    status = "partial"
                    error_message = str(error)
                    logger.warning(
                        "Snapshot interrompido por cota após %d canais: %s", processed, error
                    )
                    break
                session.commit()
                processed += 1

            # Enriquecimento roda logo após o snapshot (docs/05): sinais de
            # monetização já gravados acima, scores calculados agora.
            run_enrichment(session)
            session.commit()

        # Alertas rodam depois do cálculo de score, em sessão própria, e uma falha
        # de e-mail não pode invalidar a coleta que já deu certo.
        try:
            run_alerts_job()
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao processar alertas após o snapshot")
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
    """Registra os dois jobs diários.

    `coalesce` + `misfire_grace_time` existem porque um job diário que perde a
    hora (máquina suspensa, container reiniciando, deploy) seria simplesmente
    descartado pelo padrão do APScheduler — e o dia inteiro ficaria sem coleta
    sem ninguém perceber. Com `coalesce`, várias execuções perdidas viram uma
    só, para não gastar cota repetida de uma vez.
    """
    for job, cron, identificador in (
        (run_discovery_job, settings.discovery_cron, "discovery"),
        (run_snapshot_job, settings.snapshot_cron, "snapshot"),
    ):
        scheduler.add_job(
            job,
            CronTrigger.from_crontab(cron, timezone=settings.scheduler_timezone),
            id=identificador,
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=settings.scheduler_misfire_grace_seconds,
        )


def build_background_scheduler() -> BackgroundScheduler:
    """Scheduler para rodar dentro do processo da API (docs/07)."""
    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    _add_jobs(scheduler)
    return scheduler


def start_scheduler() -> None:
    """Roda os jobs em primeiro plano (processo dedicado)."""
    scheduler = BlockingScheduler(timezone=settings.scheduler_timezone)
    _add_jobs(scheduler)
    logger.info(
        "Scheduler iniciado — descoberta: '%s', snapshot: '%s'",
        settings.discovery_cron,
        settings.snapshot_cron,
    )
    scheduler.start()


def run_enrichment_job() -> None:
    """Recalcula os scores sem coletar nada — útil após ajustar os pesos."""
    with SessionLocal() as session:
        scored = run_enrichment(session)
        session.commit()
    logger.info("Enriquecimento manual concluído: %d canais pontuados", scored)


COMMANDS = {
    "discovery": run_discovery_job,
    "snapshot": run_snapshot_job,
    "enrichment": run_enrichment_job,
    "alerts": run_alerts_job,
    "start": start_scheduler,
}


if __name__ == "__main__":
    configure_logging()
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    if command not in COMMANDS:
        print(f"Uso: python -m src.scheduler.jobs [{'|'.join(COMMANDS)}]")
        raise SystemExit(1)
    COMMANDS[command]()

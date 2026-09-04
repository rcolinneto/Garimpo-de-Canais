import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.logging import configure_logging
from src.config.settings import settings
from src.scheduler.jobs import build_background_scheduler

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Sobe o APScheduler junto com a API (docs/07-infraestrutura-e-operacao.md).

    Uma falha aqui (ex.: cron inválido) não pode derrubar a API: o scheduler é
    opcional para servir dados, e `collection_runs` denuncia se a coleta parou.
    """
    scheduler = None
    if settings.scheduler_enabled:
        try:
            scheduler = build_background_scheduler()
            scheduler.start()
            logger.info("Scheduler de coleta iniciado")
        except Exception:  # noqa: BLE001
            scheduler = None
            logger.exception("Não foi possível iniciar o scheduler de coleta")
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Garimpo de Canais", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

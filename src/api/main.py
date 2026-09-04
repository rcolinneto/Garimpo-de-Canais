import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func

from src.api import queries
from src.api.schemas import (
    CanalDetalhe,
    CanalItem,
    HistoricoCanal,
    ListaCanais,
    NichoCreate,
    NichoHistoricoPonto,
    NichoRankingItem,
    NichoResposta,
    NichoUpdate,
    ScorePonto,
    SinalMonetizacao,
    SnapshotPonto,
    VideoRecente,
)
from src.config.logging import configure_logging
from src.config.settings import settings
from src.db.models import Channel, Niche
from src.db.session import SessionLocal
from src.scheduler.jobs import build_background_scheduler

configure_logging()
logger = logging.getLogger(__name__)


def get_session():
    with SessionLocal() as session:
        yield session


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


def _videos_do_payload(raw_payload: dict | None) -> list[VideoRecente]:
    """Últimos vídeos coletados, guardados no raw_payload do snapshot (Tela 3)."""
    if not raw_payload:
        return []
    videos = []
    for video in raw_payload.get("recent_videos", []):
        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})
        views = statistics.get("viewCount")
        videos.append(
            VideoRecente(
                video_id=video.get("id"),
                title=snippet.get("title"),
                views=int(views) if views is not None else None,
                published_at=snippet.get("publishedAt"),
            )
        )
    return videos


def _canal_base(row, sinais: list[str]) -> dict:
    return {
        "id": row.id,
        "youtube_channel_id": row.youtube_channel_id,
        "display_name": row.display_name,
        "handle": row.handle,
        "url": row.url,
        "status": row.status,
        "discovered_at": row.discovered_at,
        "niche_id": row.niche_id,
        "niche_name": row.niche_name,
        "subscriber_count": row.subscriber_count,
        "total_view_count": row.total_view_count,
        "coletado_em": row.coletado_em,
        "crescimento_7d": row.crescimento_7d,
        "crescimento_30d": row.crescimento_30d,
        "growth_score": row.growth_score,
        "monetization_score": row.monetization_score,
        "niche_virality_score": row.niche_virality_score,
        "total_score": row.total_score,
        "sinais_monetizacao": sinais,
    }


@app.get("/canais", response_model=ListaCanais)
def listar_canais(
    niche_id: int | None = None,
    min_subscribers: int | None = None,
    max_subscribers: int | None = None,
    min_growth: float | None = Query(None, description="Crescimento mínimo de inscritos em 7 dias (%)"),
    min_score: float | None = None,
    signal_types: list[str] | None = Query(
        None, description="Filtra canais com algum destes sinais de monetização"
    ),
    status: str | None = "active",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session=Depends(get_session),
) -> ListaCanais:
    """Tela 2 — canais descobertos, ordenados por total_score decrescente."""
    stmt = queries.build_channels_query(
        niche_id=niche_id,
        min_subscribers=min_subscribers,
        max_subscribers=max_subscribers,
        min_growth=min_growth,
        min_score=min_score,
        signal_types=signal_types,
        status=status,
    )
    total = queries.count_channels(session, stmt)
    rows = session.execute(stmt.limit(limit).offset(offset)).all()
    sinais = queries.signal_types_by_channel(session, [row.id for row in rows])

    return ListaCanais(
        total=total,
        limit=limit,
        offset=offset,
        items=[CanalItem(**_canal_base(row, sinais.get(row.id, []))) for row in rows],
    )


@app.get("/canais/{channel_id}", response_model=CanalDetalhe)
def detalhar_canal(channel_id: int, session=Depends(get_session)) -> CanalDetalhe:
    """Tela 3 — detalhe do canal, com evidências para conferência manual."""
    stmt = queries.build_channels_query(status=None).where(Channel.id == channel_id)
    row = session.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    sinais = queries.channel_signals(session, channel_id)
    return CanalDetalhe(
        **_canal_base(row, sorted({sinal.signal_type for sinal in sinais})),
        video_count=row.video_count,
        avg_views_last_n_videos=row.avg_views_last_n_videos,
        engagement_rate=row.engagement_rate,
        score_breakdown=row.score_breakdown,
        sinais=[
            SinalMonetizacao(
                signal_type=sinal.signal_type,
                evidence=sinal.evidence,
                confidence=sinal.confidence,
                detected_at=sinal.detected_at,
            )
            for sinal in sinais
        ],
        ultimos_videos=_videos_do_payload(row.raw_payload),
    )


@app.get("/canais/{channel_id}/historico", response_model=HistoricoCanal)
def historico_canal(
    channel_id: int,
    days: int | None = Query(None, ge=1, description="Limita o histórico aos últimos N dias"),
    session=Depends(get_session),
) -> HistoricoCanal:
    """Tela 3 — séries que alimentam os gráficos de evolução."""
    canal = session.get(Channel, channel_id)
    if canal is None:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    snapshots = queries.channel_snapshots(session, channel_id, days)
    scores = queries.channel_scores(session, channel_id, days)

    return HistoricoCanal(
        channel_id=channel_id,
        snapshots=[
            SnapshotPonto(
                collected_at=snapshot.collected_at,
                subscriber_count=snapshot.subscriber_count,
                total_view_count=snapshot.total_view_count,
                video_count=snapshot.video_count,
                avg_views_last_n_videos=snapshot.avg_views_last_n_videos,
                engagement_rate=snapshot.engagement_rate,
            )
            for snapshot in snapshots
        ],
        scores=[
            ScorePonto(
                calculated_at=score.calculated_at,
                growth_score=score.growth_score,
                monetization_score=score.monetization_score,
                niche_virality_score=score.niche_virality_score,
                total_score=score.total_score,
            )
            for score in scores
        ],
    )


@app.get("/nichos/ranking", response_model=list[NichoRankingItem])
def ranking_de_nichos(
    only_active: bool = False, session=Depends(get_session)
) -> list[NichoRankingItem]:
    """Tela 1 — radar de nichos, do que mais está bombando para o que menos."""
    return [
        NichoRankingItem(
            niche_id=row.niche_id,
            name=row.name,
            keywords=row.keywords,
            active=row.active,
            canais_ativos=row.canais_ativos,
            novos_esta_semana=row.novos_esta_semana,
            niche_virality_score=row.niche_virality_score,
            total_score_medio=row.total_score_medio,
            last_discovery_at=row.last_discovery_at,
        )
        for row in queries.niches_ranking(session, only_active=only_active)
    ]


def _normalizar_keywords(keywords: list[str]) -> list[str]:
    return [palavra.strip() for palavra in keywords if palavra.strip()]


def _nome_ja_usado(session, nome: str, ignorar_id: int | None = None) -> bool:
    query = session.query(Niche).filter(func.lower(Niche.name) == nome.lower())
    if ignorar_id is not None:
        query = query.filter(Niche.id != ignorar_id)
    return query.first() is not None


@app.post("/nichos", response_model=NichoResposta, status_code=201)
def criar_nicho(payload: NichoCreate, session=Depends(get_session)) -> Niche:
    """Tela 4 — cadastra um nicho novo."""
    nome = payload.name.strip()
    if _nome_ja_usado(session, nome):
        raise HTTPException(status_code=409, detail="Já existe um nicho com esse nome")

    nicho = Niche(
        name=nome, keywords=_normalizar_keywords(payload.keywords), active=payload.active
    )
    session.add(nicho)
    session.commit()
    session.refresh(nicho)
    logger.info("Nicho criado: %s (id=%s)", nicho.name, nicho.id)
    return nicho


@app.put("/nichos/{niche_id}", response_model=NichoResposta)
def atualizar_nicho(
    niche_id: int, payload: NichoUpdate, session=Depends(get_session)
) -> Niche:
    """Tela 4 — edita ou pausa um nicho (pausar = active=false, preserva histórico)."""
    nicho = session.get(Niche, niche_id)
    if nicho is None:
        raise HTTPException(status_code=404, detail="Nicho não encontrado")

    if payload.name is not None:
        nome = payload.name.strip()
        if _nome_ja_usado(session, nome, ignorar_id=niche_id):
            raise HTTPException(status_code=409, detail="Já existe um nicho com esse nome")
        nicho.name = nome
    if payload.keywords is not None:
        nicho.keywords = _normalizar_keywords(payload.keywords)
    if payload.active is not None:
        nicho.active = payload.active

    session.commit()
    session.refresh(nicho)
    logger.info("Nicho atualizado: %s (id=%s, active=%s)", nicho.name, nicho.id, nicho.active)
    return nicho


@app.get("/nichos/{niche_id}/historico", response_model=list[NichoHistoricoPonto])
def historico_do_nicho(
    niche_id: int,
    days: int = Query(90, ge=1, le=365),
    session=Depends(get_session),
) -> list[NichoHistoricoPonto]:
    """Tela 1 — evolução do niche_virality_score do nicho ao longo do tempo."""
    if session.get(Niche, niche_id) is None:
        raise HTTPException(status_code=404, detail="Nicho não encontrado")
    return [
        NichoHistoricoPonto(dia=row.dia, niche_virality_score=row.niche_virality_score)
        for row in queries.niche_history(session, niche_id, days)
    ]

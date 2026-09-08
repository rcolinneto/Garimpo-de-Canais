"""Consultas de leitura que sustentam as telas do dashboard (docs/06-dashboard.md).

Separadas das rotas porque envolvem SQL não-trivial: para cada canal é preciso o
snapshot mais recente, o score mais recente e os snapshots de 7 e 30 dias atrás
para calcular a taxa de crescimento exibida na Tela 2.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, and_, case, exists, func, lateral, select, true

from src.config.settings import settings
from src.db.models import (
    AlertSent,
    Channel,
    ChannelScore,
    ChannelSnapshot,
    MonetizationSignal,
    Niche,
)


def _latest_snapshots():
    """Último snapshot de cada canal (DISTINCT ON, específico do Postgres)."""
    return (
        select(
            ChannelSnapshot.channel_id.label("channel_id"),
            ChannelSnapshot.collected_at.label("collected_at"),
            ChannelSnapshot.subscriber_count.label("subscriber_count"),
            ChannelSnapshot.total_view_count.label("total_view_count"),
            ChannelSnapshot.video_count.label("video_count"),
            ChannelSnapshot.avg_views_last_n_videos.label("avg_views_last_n_videos"),
            ChannelSnapshot.engagement_rate.label("engagement_rate"),
            ChannelSnapshot.raw_payload.label("raw_payload"),
        )
        .distinct(ChannelSnapshot.channel_id)
        .order_by(ChannelSnapshot.channel_id, ChannelSnapshot.collected_at.desc())
        .subquery("latest_snapshot")
    )


def _latest_scores():
    return (
        select(
            ChannelScore.channel_id.label("channel_id"),
            ChannelScore.growth_score.label("growth_score"),
            ChannelScore.monetization_score.label("monetization_score"),
            ChannelScore.niche_virality_score.label("niche_virality_score"),
            ChannelScore.total_score.label("total_score"),
            ChannelScore.score_breakdown.label("score_breakdown"),
        )
        .distinct(ChannelScore.channel_id)
        .order_by(ChannelScore.channel_id, ChannelScore.calculated_at.desc())
        .subquery("latest_score")
    )


def _baseline(latest, days: int, name: str):
    """Snapshot de referência de N dias atrás, por canal (lateral correlacionado)."""
    return lateral(
        select(ChannelSnapshot.subscriber_count.label("subscriber_count"))
        .where(
            ChannelSnapshot.channel_id == latest.c.channel_id,
            ChannelSnapshot.collected_at <= latest.c.collected_at - timedelta(days=days),
        )
        .order_by(ChannelSnapshot.collected_at.desc())
        .limit(1),
        name=name,
    )


def _growth_expr(latest, baseline):
    """Crescimento percentual de inscritos; NULL quando não há base para comparar."""
    return (
        (latest.c.subscriber_count - baseline.c.subscriber_count)
        * 100.0
        / func.nullif(baseline.c.subscriber_count, 0)
    )


def build_channels_query(
    niche_id: int | None = None,
    min_subscribers: int | None = None,
    max_subscribers: int | None = None,
    min_growth: float | None = None,
    min_score: float | None = None,
    signal_types: list[str] | None = None,
    status: str | None = "active",
    discovered_since_days: int | None = None,
) -> Select:
    """Listagem da Tela 2, com todos os filtros descritos em docs/06."""
    latest = _latest_snapshots()
    scores = _latest_scores()
    baseline_7d = _baseline(latest, 7, "baseline_7d")
    baseline_30d = _baseline(latest, 30, "baseline_30d")

    growth_7d = _growth_expr(latest, baseline_7d)
    growth_30d = _growth_expr(latest, baseline_30d)

    stmt = (
        select(
            Channel.id.label("id"),
            Channel.youtube_channel_id,
            Channel.display_name,
            Channel.handle,
            Channel.url,
            Channel.status,
            Channel.discovered_at,
            Channel.niche_id,
            Niche.name.label("niche_name"),
            latest.c.subscriber_count,
            latest.c.total_view_count,
            latest.c.video_count,
            latest.c.avg_views_last_n_videos,
            latest.c.engagement_rate,
            latest.c.collected_at.label("coletado_em"),
            latest.c.raw_payload,
            scores.c.growth_score,
            scores.c.monetization_score,
            scores.c.niche_virality_score,
            scores.c.total_score,
            scores.c.score_breakdown,
            growth_7d.label("crescimento_7d"),
            growth_30d.label("crescimento_30d"),
        )
        .select_from(Channel)
        .join(latest, latest.c.channel_id == Channel.id)
        .outerjoin(Niche, Niche.id == Channel.niche_id)
        .outerjoin(scores, scores.c.channel_id == Channel.id)
        .outerjoin(baseline_7d, true())
        .outerjoin(baseline_30d, true())
    )

    if status:
        stmt = stmt.where(Channel.status == status)
    if niche_id is not None:
        stmt = stmt.where(Channel.niche_id == niche_id)
    if min_subscribers is not None:
        stmt = stmt.where(latest.c.subscriber_count >= min_subscribers)
    if max_subscribers is not None:
        stmt = stmt.where(latest.c.subscriber_count <= max_subscribers)
    if min_score is not None:
        stmt = stmt.where(scores.c.total_score >= min_score)
    if discovered_since_days is not None:
        # "Quais canais novos surgiram nos últimos X dias" é critério de sucesso
        # explícito em docs/01-visao-geral-e-escopo.md.
        stmt = stmt.where(
            Channel.discovered_at >= datetime.now(timezone.utc) - timedelta(days=discovered_since_days)
        )
    if min_growth is not None:
        stmt = stmt.where(growth_7d >= min_growth)
    if signal_types:
        # Mesma janela usada pelo monetization_score, para o badge exibido não
        # divergir do que de fato pontuou.
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.monetization_window_days)
        stmt = stmt.where(
            exists(
                select(MonetizationSignal.id).where(
                    MonetizationSignal.channel_id == Channel.id,
                    MonetizationSignal.signal_type.in_(signal_types),
                    MonetizationSignal.detected_at >= cutoff,
                )
            )
        )

    return stmt.order_by(scores.c.total_score.desc().nullslast(), Channel.id)


def count_channels(session, stmt: Select) -> int:
    return session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()


def signal_types_by_channel(session, channel_ids: list[int]) -> dict[int, list[str]]:
    """Badges de monetização da Tela 2, por canal."""
    if not channel_ids:
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.monetization_window_days)
    rows = session.execute(
        select(MonetizationSignal.channel_id, MonetizationSignal.signal_type)
        .where(
            MonetizationSignal.channel_id.in_(channel_ids),
            MonetizationSignal.detected_at >= cutoff,
        )
        .distinct()
    ).all()

    por_canal: dict[int, list[str]] = {}
    for channel_id, signal_type in rows:
        por_canal.setdefault(channel_id, []).append(signal_type)
    return por_canal


def channel_signals(session, channel_id: int) -> list[MonetizationSignal]:
    return (
        session.query(MonetizationSignal)
        .filter(MonetizationSignal.channel_id == channel_id)
        .order_by(MonetizationSignal.detected_at.desc(), MonetizationSignal.confidence.desc())
        .all()
    )


def channel_snapshots(session, channel_id: int, days: int | None = None) -> list[ChannelSnapshot]:
    query = session.query(ChannelSnapshot).filter(ChannelSnapshot.channel_id == channel_id)
    if days is not None:
        query = query.filter(
            ChannelSnapshot.collected_at >= datetime.now(timezone.utc) - timedelta(days=days)
        )
    return query.order_by(ChannelSnapshot.collected_at.asc()).all()


def channel_scores(session, channel_id: int, days: int | None = None) -> list[ChannelScore]:
    query = session.query(ChannelScore).filter(ChannelScore.channel_id == channel_id)
    if days is not None:
        query = query.filter(
            ChannelScore.calculated_at >= datetime.now(timezone.utc) - timedelta(days=days)
        )
    return query.order_by(ChannelScore.calculated_at.asc()).all()


def niches_ranking(session, only_active: bool = False) -> list:
    """Radar de nichos da Tela 1."""
    scores = _latest_scores()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    stmt = (
        select(
            Niche.id.label("niche_id"),
            Niche.name,
            Niche.keywords,
            Niche.active,
            Niche.last_discovery_at,
            func.count(func.distinct(Channel.id)).label("canais_ativos"),
            func.count(func.distinct(case((Channel.discovered_at >= week_ago, Channel.id)))).label(
                "novos_esta_semana"
            ),
            func.avg(scores.c.niche_virality_score).label("niche_virality_score"),
            func.avg(scores.c.total_score).label("total_score_medio"),
        )
        .select_from(Niche)
        .outerjoin(Channel, and_(Channel.niche_id == Niche.id, Channel.status == "active"))
        .outerjoin(scores, scores.c.channel_id == Channel.id)
        .group_by(Niche.id)
        .order_by(func.coalesce(func.avg(scores.c.niche_virality_score), 0).desc(), Niche.name)
    )
    if only_active:
        stmt = stmt.where(Niche.active.is_(True))
    return session.execute(stmt).all()


def alerts_sent(session, limit: int = 100) -> list:
    """Histórico de alertas disparados, com o nome do canal (Tela 5)."""
    return session.execute(
        select(
            AlertSent.id,
            AlertSent.channel_id,
            Channel.display_name.label("channel_name"),
            AlertSent.triggered_at,
            AlertSent.reason,
            AlertSent.channel_out,
        )
        .select_from(AlertSent)
        .outerjoin(Channel, Channel.id == AlertSent.channel_id)
        .order_by(AlertSent.triggered_at.desc())
        .limit(limit)
    ).all()


def niche_history(session, niche_id: int, days: int = 90) -> list:
    """Evolução do niche_virality_score ao longo do tempo (gráfico da Tela 1)."""
    dia = func.date_trunc("day", ChannelScore.calculated_at).label("dia")
    return session.execute(
        select(dia, func.avg(ChannelScore.niche_virality_score).label("niche_virality_score"))
        .select_from(ChannelScore)
        .join(Channel, Channel.id == ChannelScore.channel_id)
        .where(
            Channel.niche_id == niche_id,
            ChannelScore.calculated_at >= datetime.now(timezone.utc) - timedelta(days=days),
        )
        .group_by(dia)
        .order_by(dia)
    ).all()

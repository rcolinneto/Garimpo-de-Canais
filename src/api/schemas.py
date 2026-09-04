"""Modelos de resposta da API interna (docs/06-dashboard.md)."""

from datetime import datetime

from pydantic import BaseModel


class SinalMonetizacao(BaseModel):
    signal_type: str
    # A evidência é o que permite ao chefe conferir manualmente antes de agir.
    evidence: str | None = None
    confidence: float | None = None
    detected_at: datetime


class VideoRecente(BaseModel):
    video_id: str | None = None
    title: str | None = None
    views: int | None = None
    published_at: str | None = None


class CanalItem(BaseModel):
    id: int
    youtube_channel_id: str
    display_name: str | None = None
    handle: str | None = None
    url: str | None = None
    status: str
    discovered_at: datetime
    niche_id: int | None = None
    niche_name: str | None = None
    subscriber_count: int | None = None
    total_view_count: int | None = None
    coletado_em: datetime | None = None
    crescimento_7d: float | None = None
    crescimento_30d: float | None = None
    growth_score: float | None = None
    monetization_score: float | None = None
    niche_virality_score: float | None = None
    total_score: float | None = None
    sinais_monetizacao: list[str] = []


class ListaCanais(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CanalItem]


class CanalDetalhe(CanalItem):
    video_count: int | None = None
    avg_views_last_n_videos: float | None = None
    engagement_rate: float | None = None
    # Explica por que o canal está nessa posição do ranking.
    score_breakdown: dict | None = None
    sinais: list[SinalMonetizacao] = []
    ultimos_videos: list[VideoRecente] = []


class SnapshotPonto(BaseModel):
    collected_at: datetime
    subscriber_count: int | None = None
    total_view_count: int | None = None
    video_count: int | None = None
    avg_views_last_n_videos: float | None = None
    engagement_rate: float | None = None


class ScorePonto(BaseModel):
    calculated_at: datetime
    growth_score: float | None = None
    monetization_score: float | None = None
    niche_virality_score: float | None = None
    total_score: float | None = None


class HistoricoCanal(BaseModel):
    channel_id: int
    snapshots: list[SnapshotPonto]
    scores: list[ScorePonto]


class NichoRankingItem(BaseModel):
    niche_id: int
    name: str
    keywords: list[str] | None = None
    active: bool
    canais_ativos: int
    novos_esta_semana: int
    niche_virality_score: float | None = None
    total_score_medio: float | None = None
    last_discovery_at: datetime | None = None


class NichoHistoricoPonto(BaseModel):
    dia: datetime
    niche_virality_score: float | None = None

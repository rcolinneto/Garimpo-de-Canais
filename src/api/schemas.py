"""Modelos de requisição e resposta da API interna (docs/06-dashboard.md)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class AlertaEnviado(BaseModel):
    id: int
    channel_id: int
    channel_name: str | None = None
    triggered_at: datetime
    reason: str | None = None
    # email | dashboard_only
    channel_out: str


class AlertaConfig(BaseModel):
    """Como o alerta está configurado hoje (Tela 5)."""

    limiar: float
    email_configurado: bool
    destinatarios: list[str]


class NichoCreate(BaseModel):
    """Payload da Tela 4 ao cadastrar um nicho."""

    name: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(default_factory=list)
    active: bool = True


class NichoUpdate(BaseModel):
    """Edição parcial: só os campos enviados são alterados.

    `active=false` é como se pausa um nicho sem apagar o histórico
    (docs/03-modelo-de-dados.md).
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    keywords: list[str] | None = None
    active: bool | None = None


class NichoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    keywords: list[str] | None = None
    active: bool
    created_at: datetime
    last_discovery_at: datetime | None = None

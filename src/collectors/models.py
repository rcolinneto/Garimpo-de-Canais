from datetime import datetime

from pydantic import BaseModel, Field


class ChannelRef(BaseModel):
    """Identificação mínima de um canal, usada para trafegar entre coleta e banco."""

    youtube_channel_id: str
    handle: str | None = None
    display_name: str | None = None
    url: str | None = None


class ChannelSnapshot(BaseModel):
    """Métricas de um canal em um instante — vira uma linha de `channel_snapshots`."""

    channel_ref: ChannelRef
    collected_at: datetime
    # None (e não zero) quando o canal oculta a contagem pública de inscritos.
    subscriber_count: int | None = None
    total_view_count: int | None = None
    video_count: int | None = None
    avg_views_last_n_videos: float | None = None
    engagement_rate: float | None = None
    # Usado só pelo filtro de relevância da descoberta; não é coluna do banco,
    # vai junto no raw_payload para auditoria.
    max_recent_video_views: int | None = None
    raw_payload: dict = Field(default_factory=dict)


class ContentSignal(BaseModel):
    """Trecho de texto recente de um canal, insumo do motor de monetização (Fase 3)."""

    channel_ref: ChannelRef
    # channel_description | video_description | video_title
    source: str
    text: str
    video_id: str | None = None
    url: str | None = None
    published_at: datetime | None = None

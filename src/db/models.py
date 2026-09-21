from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Niche(Base):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Usado para rodar a descoberta em rodízio entre os nichos, já que search.list
    # é caro demais para rodar todos os nichos todo dia (docs/04-coleta-youtube.md).
    last_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    channels: Mapped[list["Channel"]] = relationship(back_populates="niche")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    youtube_channel_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    handle: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    niche_id: Mapped[int | None] = mapped_column(ForeignKey("niches.id"))
    url: Mapped[str | None] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    first_seen_subscriber_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")

    niche: Mapped[Niche | None] = relationship(back_populates="channels")
    snapshots: Mapped[list["ChannelSnapshot"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    monetization_signals: Mapped[list["MonetizationSignal"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    videos: Mapped[list["Video"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    scores: Mapped[list["ChannelScore"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    alerts_sent: Mapped[list["AlertSent"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class ChannelSnapshot(Base):
    __tablename__ = "channel_snapshots"
    __table_args__ = (
        Index("ix_channel_snapshots_channel_id_collected_at", "channel_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    subscriber_count: Mapped[int | None] = mapped_column(BigInteger)
    total_view_count: Mapped[int | None] = mapped_column(BigInteger)
    video_count: Mapped[int | None] = mapped_column(Integer)
    avg_views_last_n_videos: Mapped[float | None] = mapped_column(Numeric)
    engagement_rate: Mapped[float | None] = mapped_column(Numeric)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)

    channel: Mapped[Channel] = relationship(back_populates="snapshots")


class Video(Base):
    """Um vídeo de um canal monitorado (docs/03 e docs/05, camada de oportunidade).

    Até a Fase 7 os vídeos existiam só dentro de `channel_snapshots.raw_payload`.
    Viraram tabela porque o outlier é calculado por vídeo, e porque um vídeo
    precisa ser acompanhado ao longo do tempo — views crescem.
    """

    __tablename__ = "videos"
    __table_args__ = (Index("ix_videos_channel_id_published_at", "channel_id", "published_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    youtube_video_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Separa Short de vídeo longo: as distribuições de views não são comparáveis,
    # e misturá-las produz outlier fantasma (docs/05). Nulo = ainda desconhecido,
    # o que acontece nos vídeos recuperados do histórico de raw_payload.
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    channel: Mapped[Channel] = relationship(back_populates="videos")
    snapshots: Mapped[list["VideoSnapshot"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    outliers: Mapped[list["VideoOutlier"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class VideoSnapshot(Base):
    """Métricas de um vídeo ao longo do tempo.

    Mesma lógica de `channel_snapshots`: sem série temporal não dá para dizer se
    um vídeo *está* acelerando ou se é antigo e só acumulou views.
    """

    __tablename__ = "video_snapshots"
    __table_args__ = (
        Index("ix_video_snapshots_video_id_collected_at", "video_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)

    video: Mapped[Video] = relationship(back_populates="snapshots")


class VideoOutlier(Base):
    """Resultado do cálculo de outlier, por vídeo e por execução do motor.

    Tabela separada (e não coluna em `videos`) pelo mesmo motivo de
    `channel_scores`: o valor muda conforme canal e vídeo evoluem, e ver essa
    evolução importa.
    """

    __tablename__ = "video_outliers"
    __table_args__ = (
        Index("ix_video_outliers_video_id_calculated_at", "video_id", "calculated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Guardada para explicabilidade: o dashboard mostra contra o que o vídeo foi
    # comparado, não só o número final (docs/09 — nada de caixa-preta).
    baseline_views: Mapped[float | None] = mapped_column(Numeric)
    outlier_ratio: Mapped[float | None] = mapped_column(Numeric)
    recency_weight: Mapped[float | None] = mapped_column(Numeric)
    outlier_score: Mapped[float | None] = mapped_column(Numeric)
    breakdown: Mapped[dict | None] = mapped_column(JSONB)

    video: Mapped[Video] = relationship(back_populates="outliers")


class MonetizationSignal(Base):
    __tablename__ = "monetization_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric)

    channel: Mapped[Channel] = relationship(back_populates="monetization_signals")


class ChannelScore(Base):
    __tablename__ = "channel_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    growth_score: Mapped[float | None] = mapped_column(Numeric)
    monetization_score: Mapped[float | None] = mapped_column(Numeric)
    niche_virality_score: Mapped[float | None] = mapped_column(Numeric)
    total_score: Mapped[float | None] = mapped_column(Numeric)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB)

    channel: Mapped[Channel] = relationship(back_populates="scores")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    items_processed: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    api_units_consumed: Mapped[int | None] = mapped_column(Integer)


class AlertSent(Base):
    __tablename__ = "alerts_sent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(Text)
    channel_out: Mapped[str] = mapped_column(Text, nullable=False)

    channel: Mapped[Channel] = relationship(back_populates="alerts_sent")

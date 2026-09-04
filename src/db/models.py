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

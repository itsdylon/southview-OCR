# src/southview/db/models.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Integer, Float, DateTime, Text, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")

    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution_w: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_h: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    frame_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    upload_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="video", cascade="all, delete-orphan")
    cards: Mapped[list["Card"]] = relationship("Card", back_populates="video", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)

    job_type: Mapped[str] = mapped_column(String(30), nullable=False)  # frame_extraction / ocr / full_pipeline
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")  # queued/running/completed/failed

    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    video: Mapped["Video"] = relationship("Video", back_populates="jobs")
    cards: Mapped[list["Card"]] = relationship("Card", back_populates="job")


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("video_id", "sequence_index", name="uq_cards_video_sequence"),
        Index("ix_cards_video_id", "video_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)

    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_path: Mapped[str] = mapped_column(String, nullable=False)  # path to extracted PNG
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..N
    extracted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    video: Mapped["Video"] = relationship("Video", back_populates="cards")
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="cards")
    ocr_result: Mapped[Optional["OCRResult"]] = relationship(
        "OCRResult", back_populates="card", cascade="all, delete-orphan", uselist=False
    )

 

class OCRResult(Base):
    __tablename__ = "ocr_results"
    __table_args__ = (
        Index("ix_ocr_results_review_status", "review_status"),
        Index("ix_ocr_results_confidence_score", "confidence_score"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    card_id: Mapped[str] = mapped_column(String(36), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, unique=True)

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_fields_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    word_confidences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON if you want

    ocr_engine_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # minimal fields for this phase
    deceased_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date_of_death: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    card: Mapped["Card"] = relationship("Card", back_populates="ocr_result")
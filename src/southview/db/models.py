"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Video(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default="uploaded")
    duration_seconds = Column(Float, nullable=True)
    resolution_w = Column(Integer, nullable=True)
    resolution_h = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    upload_timestamp = Column(DateTime, nullable=False, default=_utcnow)
    metadata_json = Column(Text, nullable=True)

    jobs = relationship("Job", back_populates="video", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="video", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)
    job_type = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    progress = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    video = relationship("Video", back_populates="jobs")

    __table_args__ = (
        Index("ix_jobs_video_id", "video_id"),
        Index("ix_jobs_status", "status"),
    )


class Card(Base):
    __tablename__ = "cards"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    frame_number = Column(Integer, nullable=False)
    image_path = Column(String, nullable=False)
    sequence_index = Column(Integer, nullable=False)
    extracted_at = Column(DateTime, nullable=False, default=_utcnow)

    video = relationship("Video", back_populates="cards")
    ocr_result = relationship(
        "OCRResult", back_populates="card", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("video_id", "sequence_index", name="uq_card_video_seq"),
        Index("ix_cards_video_id", "video_id"),
    )


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    card_id = Column(String(36), ForeignKey("cards.id"), unique=True, nullable=False)
    raw_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=False)
    word_confidences = Column(Text, nullable=True)  # JSON
    ocr_engine_version = Column(String, nullable=True)
    processed_at = Column(DateTime, nullable=False, default=_utcnow)
    review_status = Column(String(20), nullable=False, default="pending")
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Original OCR-extracted field values before any review edits (audit trail)
    raw_fields_json = Column(Text, nullable=True)

    # Structured card fields (current values — OCR-extracted, then corrected by reviewer)
    deceased_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    owner = Column(String, nullable=True)
    relation = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    date_of_death = Column(String, nullable=True)
    date_of_burial = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    sex = Column(String(10), nullable=True)
    age = Column(String(10), nullable=True)
    grave_type = Column(String, nullable=True)
    grave_fee = Column(String, nullable=True)
    undertaker = Column(String, nullable=True)
    board_of_health_no = Column(String, nullable=True)
    svc_no = Column(String, nullable=True)

    card = relationship("Card", back_populates="ocr_result")

    __table_args__ = (
        Index("ix_ocr_results_review_status", "review_status"),
        Index("ix_ocr_results_confidence", "confidence_score"),
    )

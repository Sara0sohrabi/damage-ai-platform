"""Persistence layer for vehicle evidence and expert-reviewed assessments."""
from __future__ import annotations

import json
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("VEHICLE_VISION_DATABASE_URL") or os.getenv(
    "DATABASE_URL", "sqlite:///./vehicle_vision.db"
)
_engine_options = {"pool_pre_ping": True} if DATABASE_URL.startswith("postgresql") else {"connect_args": {"check_same_thread": False}}
engine = create_engine(DATABASE_URL, **_engine_options)

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS vehicle_claim_media (
        media_id VARCHAR(36) PRIMARY KEY, claim_id VARCHAR(160) NOT NULL,
        storage_key TEXT NOT NULL, filename TEXT, content_type VARCHAR(80) NOT NULL,
        size_bytes BIGINT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS vehicle_vision_analyses (
        analysis_id VARCHAR(36) PRIMARY KEY, claim_id VARCHAR(160) NOT NULL,
        media_id VARCHAR(36) NOT NULL, model_version VARCHAR(120) NOT NULL,
        device VARCHAR(30), detections_json TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS vehicle_assessment_reviews (
        assessment_id VARCHAR(36) PRIMARY KEY, claim_id VARCHAR(160) NOT NULL,
        reviewer VARCHAR(150) NOT NULL, notes TEXT, approved BOOLEAN NOT NULL,
        items_json TEXT NOT NULL, total_estimate_irr BIGINT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
]


def initialize_database() -> None:
    with engine.begin() as connection:
        for statement in SCHEMA:
            connection.execute(text(statement))


def create_media(*, media_id, claim_id, storage_key, filename, content_type, size_bytes, width, height):
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO vehicle_claim_media
            (media_id, claim_id, storage_key, filename, content_type, size_bytes, width, height)
            VALUES (:media_id, :claim_id, :storage_key, :filename, :content_type, :size_bytes, :width, :height)
        """), locals())


def save_analysis(*, analysis_id, claim_id, media_id, model_version, device, detections):
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO vehicle_vision_analyses
            (analysis_id, claim_id, media_id, model_version, device, detections_json)
            VALUES (:analysis_id, :claim_id, :media_id, :model_version, :device, :detections_json)
        """), {
            "analysis_id": analysis_id, "claim_id": claim_id, "media_id": media_id,
            "model_version": model_version, "device": device,
            "detections_json": json.dumps(detections, ensure_ascii=False),
        })


def get_claim_results(claim_id: str):
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT analysis_id, media_id, model_version, device, detections_json, created_at
            FROM vehicle_vision_analyses WHERE claim_id = :claim_id
            ORDER BY created_at DESC
        """), {"claim_id": claim_id}).mappings().all()
    return [{
        "analysis_id": row["analysis_id"], "media_id": row["media_id"],
        "model_version": row["model_version"], "device": row["device"],
        "detections": json.loads(row["detections_json"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    } for row in rows]


def create_assessment(*, assessment_id, claim_id, reviewer, notes, approved, items, total_estimate_irr):
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO vehicle_assessment_reviews
            (assessment_id, claim_id, reviewer, notes, approved, items_json, total_estimate_irr)
            VALUES (:assessment_id, :claim_id, :reviewer, :notes, :approved, :items_json, :total_estimate_irr)
        """), {
            "assessment_id": assessment_id, "claim_id": claim_id, "reviewer": reviewer,
            "notes": notes, "approved": approved,
            "items_json": json.dumps(items, ensure_ascii=False),
            "total_estimate_irr": total_estimate_irr,
        })

"""YOLO inference adapter for vehicle parts and damage.

Weights are intentionally external: trained model files are not committed to Git.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PIL import Image


class ModelNotConfigured(RuntimeError):
    """Raised when no trained vehicle-vision weights are available."""


class VehicleVisionModel:
    def __init__(self) -> None:
        self.model_path = Path(
            os.getenv("VEHICLE_VISION_MODEL", "models/vehicle_vision/vehicle_damage_yolo.pt")
        )
        self.confidence = float(os.getenv("VEHICLE_VISION_CONFIDENCE", "0.25"))
        self._model: Any | None = None
        self._device = self._select_device()

    @staticmethod
    def _select_device() -> str:
        # Apple Silicon: prefer PyTorch MPS; Docker/other hosts fall back to CPU.
        try:
            import torch

            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            if torch.cuda.is_available():
                return "0"
        except Exception:
            pass
        return "cpu"

    @property
    def ready(self) -> bool:
        return self.model_path.is_file()

    def load(self) -> None:
        if not self.ready:
            raise ModelNotConfigured(
                f"Trained weights not found at {self.model_path}. "
                "Train/export a vehicle damage model before enabling inference."
            )
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise RuntimeError(
                    "Ultralytics is not installed. Install services/vehicle_vision/requirements.txt"
                ) from exc
            self._model = YOLO(str(self.model_path))

    def predict(self, image: Image.Image) -> list[dict[str, Any]]:
        self.load()
        results = self._model.predict(
            source=image,
            conf=self.confidence,
            device=self._device,
            verbose=False,
        )
        detections: list[dict[str, Any]] = []
        for result in results:
            names = result.names or {}
            boxes = result.boxes
            if boxes is None:
                continue
            polygons = (
                result.masks.xy
                if result.masks is not None
                else [None] * len(boxes)
            )
            for index, box in enumerate(boxes):
                class_id = int(box.cls.item())
                xyxy = [round(float(v), 2) for v in box.xyxy[0].tolist()]
                polygon = polygons[index] if index < len(polygons) else None
                detections.append(
                    {
                        "class_id": class_id,
                        "class_name": str(names.get(class_id, class_id)),
                        "confidence": round(float(box.conf.item()), 4),
                        "bbox_xyxy": xyxy,
                        "segmentation": (
                            [[round(float(x), 2), round(float(y), 2)] for x, y in polygon.tolist()]
                            if polygon is not None
                            else None
                        ),
                    }
                )
        return detections

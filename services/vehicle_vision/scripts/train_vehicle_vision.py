"""Train the vehicle-part/damage detector with Ultralytics YOLO.

Dataset must follow YOLO detection layout and use the class order in
data/vehicle_vision/damage_dataset.yaml.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import torch
from ultralytics import YOLO


def choose_device(requested: str) -> str:
    if requested != "auto":
        return requested
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "0"
    return "cpu"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/vehicle_vision/damage_dataset.yaml")
    parser.add_argument("--weights", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", default="models/vehicle_vision/vehicle_damage_yolo.pt")
    args = parser.parse_args()

    dataset = Path(args.data)
    if not dataset.is_file():
        raise SystemExit(f"Dataset YAML not found: {dataset}")
    device = choose_device(args.device)
    model = YOLO(args.weights)
    result = model.train(
        data=str(dataset), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        device=device, project="runs/vehicle_vision", name="damage_detector",
        exist_ok=True, patience=20, seed=42,
    )
    best = Path(result.save_dir) / "weights" / "best.pt"
    if not best.is_file():
        raise SystemExit(f"Training finished but best checkpoint is missing: {best}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, output)
    print(f"device={device}")
    print(f"best_model={output}")


if __name__ == "__main__":
    main()

# Vehicle damage dataset preparation

The repository does not include public-dataset images or trained weights. Obtain datasets only where their license permits commercial/insurance use, keep source/license records, and do not upload private claimant images to public repositories.

## YOLO layout

```text
data/vehicle_vision/dataset/
  images/{train,val,test}/
  labels/{train,val,test}/
```

Set the absolute dataset root in `damage_dataset.yaml` (or edit its `path`). Every image needs a matching YOLO label text file. Use the exact class IDs and class order from that YAML.

## Annotation rules

- Label visible body parts and damage regions separately; do not label an unseen or inferred defect.
- Draw tight boxes around the visible object/damage. Use segmentation only if the dataset and annotation tool support it consistently.
- Record source dataset, source URL, license, collection date, annotation schema version and annotator.
- Split by claim/vehicle identity, not random image, to prevent near-duplicate views of one vehicle leaking across train and test.
- Keep a separate Iranian validation set containing local vehicle makes, lighting, road/weather conditions and common repair cases.
- Review class imbalance and report per-class precision, recall, mAP50 and mAP50-95. A detector score is not a damage severity or repair-cost estimate.

## Training

From the repository root:

```bash
pip install -r services/vehicle_vision/requirements.txt
python -m services.vehicle_vision.scripts.train_vehicle_vision --data data/vehicle_vision/damage_dataset.yaml --epochs 100
```

On Apple Silicon the script selects MPS when available; otherwise it uses CUDA or CPU. The best checkpoint is copied to `models/vehicle_vision/vehicle_damage_yolo.pt`.

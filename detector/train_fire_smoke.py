"""Train a YOLO fire & smoke detector (much more accurate than the colour heuristic).

1. Download a labelled dataset in YOLO format, e.g. D-Fire
   (https://github.com/gaiasd/DFireDataset - classes: 0 smoke, 1 fire),
   and arrange it as described in fire_smoke_data.yaml.
2. python train_fire_smoke.py --data fire_smoke_data.yaml --epochs 50
3. Set FIRE_SMOKE_MODEL=runs/fire_smoke/train/weights/best.pt in detector/.env
"""
import argparse
from pathlib import Path

from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="fire_smoke_data.yaml")
    ap.add_argument("--base", default="yolo11n.pt", help="pretrained checkpoint to fine-tune")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--fraction", type=float, default=1.0, help="use only this fraction of the training images")
    args = ap.parse_args()

    model = YOLO(args.base)
    model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                device=args.device, workers=args.workers, fraction=args.fraction,
                project=str(Path(__file__).parent / "runs" / "fire_smoke"), name="train", exist_ok=True, patience=15)
    metrics = model.val()
    print("mAP50-95:", metrics.box.map, "mAP50:", metrics.box.map50)
    print("Best weights: runs/fire_smoke/train/weights/best.pt")


if __name__ == "__main__":
    main()

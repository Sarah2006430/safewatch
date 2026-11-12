"""Build a balanced YOLO training subset from a fire/smoke dataset zip (Roboflow / D-Fire YOLO layout).

Training on all ~30k images needs a GPU; on a laptop CPU a balanced subset of a few
thousand images trains in about an hour and is far more accurate than the colour heuristic.

    python prepare_fire_training.py C:/Users/me/safewatch-data/fire_smoke_dataset.zip \
        --out C:/Users/me/safewatch-data/fire_subset --train 4000 --val 800
    python train_fire_smoke.py --data C:/Users/me/safewatch-data/fire_subset/data.yaml --epochs 15 --imgsz 416
"""
import argparse
import random
import zipfile
from pathlib import Path


def classes_of(label_text: str) -> set[int]:
    return {int(line.split()[0]) for line in label_text.splitlines() if line.strip()}


def pick(z: zipfile.ZipFile, split: str, n: int, names: list[str], rng: random.Random) -> list[str]:
    labels = [x for x in z.namelist() if x.startswith(f"{split}/labels/") and x.endswith(".txt")]
    buckets = {"both": [], **{nm: [] for nm in names}, "none": []}
    for lab in labels:
        cls = classes_of(z.read(lab).decode("utf-8", "ignore"))
        key = "none" if not cls else "both" if len(cls) > 1 else names[next(iter(cls))]
        buckets[key].append(lab)
    for b in buckets.values():
        rng.shuffle(b)
    # 30% fire-only, 30% smoke-only, 20% both, 20% negatives (fills from others if short)
    share = {names[0]: .3, names[1]: .3, "both": .2, "none": .2}
    chosen = []
    for k, frac in share.items():
        chosen += buckets[k][: int(n * frac)]
    rest = [x for b in buckets.values() for x in b if x not in set(chosen)]
    chosen += rest[: max(0, n - len(chosen))]
    print(f"  {split}: " + ", ".join(f"{k}={len(v)}" for k, v in buckets.items()) + f" -> picked {len(chosen)}")
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--train", type=int, default=4000)
    ap.add_argument("--val", type=int, default=800)
    ap.add_argument("--names", default="Fire,Smoke", help="class names in label-id order")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    names = a.names.split(",")
    rng = random.Random(a.seed)
    out = Path(a.out)
    z = zipfile.ZipFile(a.zip)
    all_names = set(z.namelist())
    for split, n, dst in (("train", a.train, "train"), ("valid", a.val, "val")):
        for lab in pick(z, split, n, names, rng):
            stem = Path(lab).stem
            img = next((f"{split}/images/{stem}{ext}" for ext in (".jpg", ".jpeg", ".png") if f"{split}/images/{stem}{ext}" in all_names), None)
            if not img:
                continue
            for src, sub in ((img, "images"), (lab, "labels")):
                p = out / dst / sub / Path(src).name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(src))
    (out / "data.yaml").write_text(
        f"path: {out.as_posix()}\ntrain: train/images\nval: val/images\nnames:\n"
        + "".join(f"  {i}: {nm.lower()}\n" for i, nm in enumerate(names)), encoding="utf-8")
    print("wrote", out / "data.yaml")


if __name__ == "__main__":
    main()

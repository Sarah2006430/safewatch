"""Benchmark the detectors clip-by-clip on the public datasets and write a report.

A positive clip counts as detected if the expected alert fires at least once; a
negative (control) clip counts as a false alarm if that alert fires at all.

    python benchmark_datasets.py                      # all suites
    python benchmark_datasets.py --suite falls fire   # a subset

Writes datasets/benchmark.json and ../frontend/public/benchmark.json (shown on the Analytics page).
"""
import argparse
import glob
import json
import os
import tempfile
import time

from config import settings
from evaluate_video import evaluate
from prepare_demo_videos import build

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "datasets", "raw")


def suites():
    r = lambda pat: sorted(glob.glob(os.path.join(RAW, pat)))  # noqa: E731
    return {
        "falls": dict(title="Person fall", alert="fall", detect=["fall"], prep=dict(hold_seconds=3.0, crop=True),
                      dataset="UR Fall Detection Dataset (Univ. of Rzeszow)",
                      pos=r("fall-*-cam0.mp4"), neg=r("adl-*-cam0.mp4")),
        "fire": dict(title="Fire", alert="fire", detect=["fire"], prep=dict(max_seconds=25),
                     dataset="FIRESENSE flame videos (CERTH / Bilkent, CC-BY 4.0)",
                     pos=r("fire/pos/*.avi"), neg=r("fire/neg/*.avi")),
        "smoke": dict(title="Smoke", alert="smoke", detect=["smoke"], prep=dict(max_seconds=25),
                      dataset="FIRESENSE smoke videos (CERTH / Bilkent, CC-BY 4.0)",
                      pos=r("smoke/pos/*.avi"), neg=r("smoke/neg/*.avi")),
    }


def run_suite(name, s, tmp):
    def one(path):
        clip = os.path.join(tmp, f"{name}-{os.path.basename(path)}.mp4")
        if not os.path.exists(clip):
            build(clip, [path], gap_seconds=0, **s["prep"])
        hits = [d for _, d in evaluate(clip, s["detect"], quiet=True) if d.type == s["alert"]]
        return {"clip": os.path.basename(path), "alerts": len(hits),
                "confidence": round(max((d.confidence for d in hits), default=0), 2)}

    pos = [one(p) for p in s["pos"]]
    neg = [one(p) for p in s["neg"]]
    tp = sum(1 for c in pos if c["alerts"])
    fp = sum(1 for c in neg if c["alerts"])
    res = {
        "suite": name, "title": s["title"], "dataset": s["dataset"],
        "positives": len(pos), "detected": tp, "recall": round(tp / len(pos), 3) if pos else None,
        "negatives": len(neg), "false_alarm_clips": fp, "false_alarm_rate": round(fp / len(neg), 3) if neg else None,
        "clips": {"positive": pos, "negative": neg},
    }
    print(f"{s['title']:12s} detected {tp}/{len(pos)}   false alarms {fp}/{len(neg)} control clips")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", nargs="+", choices=list(suites()))
    a = ap.parse_args()
    all_suites = suites()
    tmp = os.path.join(tempfile.gettempdir(), "safewatch-bench")
    os.makedirs(tmp, exist_ok=True)
    out_path = os.path.join(HERE, "datasets", "benchmark.json")
    report = {"results": []}
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            report = json.load(f)
    keep = {r["suite"]: r for r in report.get("results", [])}
    for name in a.suite or all_suites:
        if all_suites[name]["pos"]:
            keep[name] = run_suite(name, all_suites[name], tmp)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "models": {"pose": settings.pose_model, "fire_smoke": settings.fire_smoke_model or "OpenCV colour/motion heuristic",
                   "person_conf": settings.person_conf},
        "results": [keep[k] for k in all_suites if k in keep],
    }
    for path in (out_path, os.path.join(HERE, "..", "frontend", "public", "benchmark.json")):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    print("wrote", out_path)


if __name__ == "__main__":
    main()

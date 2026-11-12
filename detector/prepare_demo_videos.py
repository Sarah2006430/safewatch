"""Turn public research datasets into looping "camera feeds" for the detector.

Every frame comes from real recorded footage; nothing is synthesised. Sources:

* UR Fall Detection Dataset - University of Rzeszow (Kwolek & Kepski, 2014)
  http://fenix.ur.edu.pl/~mkepski/ds/uf.html  (fall-XX-cam0 / adl-XX-cam0; RGB half used)
* FIRESENSE flame & smoke video database - CERTH / Bilkent University, CC-BY 4.0
  https://zenodo.org/records/836749

    python prepare_demo_videos.py            # reads datasets/raw, writes datasets/demo
"""
import argparse
import glob
import os

import cv2
import numpy as np

W, H, FPS = 640, 480, 25


def letterbox(frame, w=W, h=H):
    fh, fw = frame.shape[:2]
    s = min(w / fw, h / fh)
    nw, nh = int(fw * s), int(fh * s)
    out = np.zeros((h, w, 3), np.uint8)
    x, y = (w - nw) // 2, (h - nh) // 2
    out[y:y + nh, x:x + nw] = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    return out


def frames(path, crop_right_half=False, max_seconds=None):
    cap = cv2.VideoCapture(path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    step = src_fps / FPS
    i, nxt, n = 0, 0.0, 0
    limit = int(max_seconds * FPS) if max_seconds else None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i >= nxt:
            nxt += step
            if crop_right_half:
                f = f[:, f.shape[1] // 2:]
            yield letterbox(f)
            n += 1
            if limit and n >= limit:
                break
        i += 1
    cap.release()


def build(out_path, clips, hold_seconds=0.0, gap_seconds=0.6, crop=False, max_seconds=None):
    if not clips:
        print("  (no input clips for", out_path, ")")
        return
    vw = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    total = 0
    for c in clips:
        last = None
        for f in frames(c, crop, max_seconds):
            vw.write(f)
            last = f
            total += 1
        # UR Fall clips stop ~0.5 s after the person lands; hold the final real frame
        # (the person is still on the floor) so the 1 s "stays down" rule can be evaluated.
        for _ in range(int(hold_seconds * FPS)):
            if last is not None:
                vw.write(last)
                total += 1
        for _ in range(int(gap_seconds * FPS)):
            vw.write(np.zeros((H, W, 3), np.uint8))
            total += 1
    vw.release()
    to_h264(out_path)
    print(f"  {out_path}: {len(clips)} clips, {total / FPS:.0f} s")


def to_h264(path):
    """Re-encode to H.264 so the files also play in browsers / Windows players (and are ~5x smaller)."""
    try:
        import subprocess
        import imageio_ffmpeg
        tmp = path + ".tmp.mp4"
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-i", path, "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", tmp],
                       check=True)
        os.replace(tmp, path)
    except Exception as e:  # keep the OpenCV-encoded file if ffmpeg is unavailable
        print("  (H.264 re-encode skipped:", e, ")")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="datasets/raw")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo-recordings", "feeds"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    r = lambda pat: sorted(glob.glob(os.path.join(a.raw, pat)))  # noqa: E731

    print("Building demo feeds from real footage:")
    build(os.path.join(a.out, "falls_ur_room.mp4"), r("fall-*-cam0.mp4"), hold_seconds=3.0, crop=True)
    build(os.path.join(a.out, "restricted_ur_room.mp4"), r("adl-*-cam0.mp4"), gap_seconds=0.3, crop=True)
    build(os.path.join(a.out, "fire_firesense.mp4"), r("fire/pos/*.avi"), max_seconds=25)
    build(os.path.join(a.out, "smoke_firesense.mp4"), r("smoke/pos/*.avi"), max_seconds=25)
    water = r("water/*.*")
    if water:
        build(os.path.join(a.out, "water_swimmers.mp4"), water, max_seconds=60)


if __name__ == "__main__":
    main()

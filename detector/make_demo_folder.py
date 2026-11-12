"""Assemble ../demo-recordings: everything needed to show SafeWatch working in a presentation.

    demo-recordings/
      feeds/      long looping "camera" videos the detector analyses live (registered as cameras)
      import/     short single-event clips to upload live via Cameras -> Import recording
      evidence/   evidence clips + snapshots that SafeWatch itself recorded when it raised alerts
      README.txt  what each file is, where it comes from and its licence

    python make_demo_folder.py                 # (re)build import/ clips and the README
    python make_demo_folder.py --evidence 9 10 7 8   # also copy evidence of these incident ids
"""
import argparse
import glob
import os
import shutil

from prepare_demo_videos import build

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "demo-recordings"))
RAW = os.path.join(HERE, "datasets", "raw")
MEDIA = os.path.abspath(os.path.join(HERE, "..", "backend", "media", "incidents"))

IMPORT_CLIPS = [
    # (output name, source, prep options, what it shows)
    ("fall_single_UR-fall-01.mp4", "fall-01-cam0.mp4", dict(hold_seconds=4.0, crop=True), "One person falls in an office (expect FALL)"),
    ("fall_single_UR-fall-07.mp4", "fall-07-cam0.mp4", dict(hold_seconds=4.0, crop=True), "Person falls next to a chair (expect FALL)"),
    ("fire_single_FIRESENSE-pos2.mp4", "fire/pos/posVideo2.871.avi", dict(max_seconds=20), "Open flames (expect FIRE)"),
    ("smoke_single_FIRESENSE-pos9.mp4", "smoke/pos/testpos09.825.avi", dict(max_seconds=28), "Smoke plume (expect SMOKE)"),
    ("intrusion_walkin_UR-adl-01.mp4", "adl-01-cam0.mp4", dict(crop=True), "Person walks through a room - draw a restricted zone (expect INTRUSION)"),
    ("control_no_fire_FIRESENSE-neg6.mp4", "fire/neg/negsVideo6.863.avi", dict(max_seconds=30), "Control: no fire/smoke (should stay quiet)"),
]

README = """SafeWatch - demo recordings
===========================

All footage is real recorded video from public research datasets - nothing is staged or synthetic.
SafeWatch analyses it exactly like a live CCTV/RTSP stream: YOLO looks at every frame in real time.

feeds/  (already registered as cameras on the map - they loop continuously)
  falls_ur_room.mp4         30 real falls ........................ Care Home - Ward 3
  restricted_ur_room.mp4    15 everyday-activity clips ........... Data Centre - Server Hall Door (restricted zone on the doorway)
  fire_firesense.mp4        11 real fire videos .................. Industrial Yard - North
  smoke_firesense.mp4       13 real smoke videos ................. Hillside Watchtower
  water_swimmers.mp4        swimmers in a bog pool (aerial) ...... Lakeside Promenade

import/  (short clips to upload LIVE during the demo: Cameras -> Import recording)
{imports}

evidence/  (recorded automatically by SafeWatch when it raised each alert: 5 s before + 6 s after)
{evidence}

Sources and licences
  UR Fall Detection Dataset - B. Kwolek, M. Kepski, University of Rzeszow (2014)
      http://fenix.ur.edu.pl/~mkepski/ds/uf.html   (RGB half of the cam0 recordings is used)
  FIRESENSE flame & smoke video database - CERTH / Bilkent University - CC-BY 4.0
      https://zenodo.org/records/836749
  "Swimmers in Ohepalu bog pool, July 2021" - Wikimedia Commons, Sillerkiil - CC0
      https://commons.wikimedia.org/wiki/File:Swimmers_in_Ohepalu_bog_pool,_July_2021.webm
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", nargs="*", type=int, default=[])
    a = ap.parse_args()
    for sub in ("feeds", "import", "evidence"):
        os.makedirs(os.path.join(ROOT, sub), exist_ok=True)

    lines = []
    for out, src, prep, what in IMPORT_CLIPS:
        dst = os.path.join(ROOT, "import", out)
        if not os.path.exists(dst) and os.path.exists(os.path.join(RAW, src)):
            build(dst, [os.path.join(RAW, src)], gap_seconds=0, **prep)
        lines.append(f"  {out:38s} {what}")

    for inc in a.evidence:
        folder = os.path.join(MEDIA, str(inc))
        for f in glob.glob(os.path.join(folder, "*")):
            name = f"incident{inc:04d}_" + ("evidence_clip.mp4" if f.endswith(".mp4") else os.path.basename(f))
            shutil.copy2(f, os.path.join(ROOT, "evidence", name))
    ev = sorted(os.listdir(os.path.join(ROOT, "evidence")))
    evidence = "\n".join(f"  {e}" for e in ev) or "  (none yet)"

    with open(os.path.join(ROOT, "README.txt"), "w", encoding="utf-8") as f:
        f.write(README.format(imports="\n".join(lines), evidence=evidence))
    print("demo folder:", ROOT)


if __name__ == "__main__":
    main()

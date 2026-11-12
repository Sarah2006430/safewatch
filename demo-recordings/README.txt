SafeWatch - demo recordings
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
  fall_single_UR-fall-01.mp4             One person falls in an office (expect FALL)
  fall_single_UR-fall-07.mp4             Person falls next to a chair (expect FALL)
  fire_single_FIRESENSE-pos2.mp4         Open flames (expect FIRE)
  smoke_single_FIRESENSE-pos9.mp4        Smoke plume (expect SMOKE)
  intrusion_walkin_UR-adl-01.mp4         Person walks through a room - draw a restricted zone (expect INTRUSION)
  control_no_fire_FIRESENSE-neg6.mp4     Control: no fire/smoke (should stay quiet)

evidence/  (recorded automatically by SafeWatch when it raised each alert: 5 s before + 6 s after)
  incident0007_evidence_clip.mp4
  incident0007_snapshot.jpg
  incident0008_evidence_clip.mp4
  incident0008_snapshot.jpg
  incident0009_evidence_clip.mp4
  incident0009_snapshot.jpg
  incident0010_evidence_clip.mp4
  incident0010_snapshot.jpg

Sources and licences
  UR Fall Detection Dataset - B. Kwolek, M. Kepski, University of Rzeszow (2014)
      http://fenix.ur.edu.pl/~mkepski/ds/uf.html   (RGB half of the cam0 recordings is used)
  FIRESENSE flame & smoke video database - CERTH / Bilkent University - CC-BY 4.0
      https://zenodo.org/records/836749
  "Swimmers in Ohepalu bog pool, July 2021" - Wikimedia Commons, Sillerkiil - CC0
      https://commons.wikimedia.org/wiki/File:Swimmers_in_Ohepalu_bog_pool,_July_2021.webm

"""Unit tests for the detection logic using synthetic people / frames.

Run from the detector folder:  python -m unittest discover tests
(These do not need YOLO / a camera.)
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzers.fall import FallAnalyzer  # noqa: E402
from analyzers.intrusion import IntrusionAnalyzer  # noqa: E402
from analyzers.water import WaterDistressAnalyzer  # noqa: E402
from geometry import GeoMapper, Person, build_zones  # noqa: E402


def kpts_upright(x, y, h):
    """Standing person: head at top, shoulders, hips, knees, ankles stacked vertically."""
    k = np.zeros((17, 3))
    k[:, 2] = 0.9
    k[0] = [x, y + 0.08 * h, 0.9]
    k[1], k[2] = [x - 3, y + 0.06 * h, .9], [x + 3, y + 0.06 * h, .9]
    k[5], k[6] = [x - 15, y + 0.2 * h, .9], [x + 15, y + 0.2 * h, .9]
    k[7], k[8] = [x - 18, y + 0.35 * h, .9], [x + 18, y + 0.35 * h, .9]
    k[9], k[10] = [x - 18, y + 0.48 * h, .9], [x + 18, y + 0.48 * h, .9]
    k[11], k[12] = [x - 10, y + 0.5 * h, .9], [x + 10, y + 0.5 * h, .9]
    k[13], k[14] = [x - 10, y + 0.75 * h, .9], [x + 10, y + 0.75 * h, .9]
    k[15], k[16] = [x - 10, y + h, .9], [x + 10, y + h, .9]
    return k


def kpts_lying(x, y, w):
    """Person lying horizontally: body axis along x."""
    k = np.zeros((17, 3))
    k[:, 2] = 0.9
    k[0] = [x, y, .9]
    k[5], k[6] = [x + 0.2 * w, y - 8, .9], [x + 0.2 * w, y + 8, .9]
    k[11], k[12] = [x + 0.5 * w, y - 6, .9], [x + 0.5 * w, y + 6, .9]
    k[15], k[16] = [x + w, y - 5, .9], [x + w, y + 5, .9]
    return k


class FallTests(unittest.TestCase):
    def test_fall_detected_after_upright_to_lying(self):
        fa = FallAnalyzer(confirm_seconds=1.0)
        t = 0.0
        out = []
        for _ in range(10):  # standing for 1s
            out += fa.update([Person(1, (100, 100, 160, 300), 0.9, kpts_upright(130, 100, 200))], t)
            t += 0.1
        for _ in range(15):  # lying for 1.5s
            out += fa.update([Person(1, (60, 260, 260, 310), 0.9, kpts_lying(60, 285, 200))], t)
            t += 0.1
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].type, "fall")
        self.assertEqual(out[0].details["kind"], "fall")
        self.assertGreater(out[0].confidence, 0.6)

    def test_standing_person_no_alert(self):
        fa = FallAnalyzer()
        out = []
        for i in range(50):
            out += fa.update([Person(1, (100, 100, 160, 300), 0.9, kpts_upright(130, 100, 200))], i * 0.1)
        self.assertEqual(out, [])


class IntrusionTests(unittest.TestCase):
    def test_intrusion_after_dwell(self):
        zones = build_zones([{"id": 1, "name": "Vault", "kind": "restricted", "dwell_seconds": 1.0,
                              "roi": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]]}], 1000, 500)
        ia = IntrusionAnalyzer()
        out = []
        for i in range(20):
            out += ia.update([Person(7, (700, 100, 760, 300), 0.9)], zones, i * 0.1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].details["zone"], "Vault")

    def test_outside_zone_no_alert(self):
        zones = build_zones([{"id": 1, "name": "Vault", "kind": "restricted", "dwell_seconds": 0.5,
                              "roi": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]]}], 1000, 500)
        ia = IntrusionAnalyzer()
        out = []
        for i in range(20):
            out += ia.update([Person(7, (100, 100, 160, 300), 0.9)], zones, i * 0.1)
        self.assertEqual(out, [])


class WaterTests(unittest.TestCase):
    def zones(self):
        return build_zones([{"id": 2, "name": "Lake", "kind": "water", "dwell_seconds": 1.0,
                             "roi": [[0, 0.4], [1, 0.4], [1, 1], [0, 1]]}], 1000, 500)

    def test_submerged_waving_person_raises_distress(self):
        wa = WaterDistressAnalyzer()
        out = []
        for i in range(50):
            t = i * 0.1
            bob = 15 * np.sin(i)
            k = np.zeros((17, 3))
            k[0] = [500, 300 + bob, 0.9]
            k[1], k[2] = [495, 297 + bob, .9], [505, 297 + bob, .9]
            k[5], k[6] = [485, 320 + bob, .9], [515, 320 + bob, .9]
            k[9], k[10] = [470, 270 + bob, .9], [530, 270 + bob, .9]  # wrists above shoulders
            out += wa.update([Person(3, (460, 260 + bob, 540, 340 + bob), 0.8, k)], self.zones(), t, (500, 1000))
        self.assertTrue(any(d.details.get("kind") == "distress_behaviour" for d in out))

    def test_person_disappearing_in_water(self):
        wa = WaterDistressAnalyzer()
        out = []
        for i in range(30):
            out += wa.update([Person(4, (480, 280, 520, 340), 0.8)], self.zones(), i * 0.1, (500, 1000))
        for i in range(30, 80):
            out += wa.update([], self.zones(), i * 0.1, (500, 1000))
        self.assertTrue(any(d.details.get("kind") == "possible_submersion" for d in out))


class GeoTests(unittest.TestCase):
    def test_homography_corners(self):
        cal = {"image": [[0, 0], [1, 0], [1, 1], [0, 1]],
               "geo": [[12.0, 77.0], [12.0, 77.001], [11.999, 77.001], [11.999, 77.0]]}
        m = GeoMapper(cal, 1000, 500)
        lat, lon = m.to_latlon((1000, 500))
        self.assertAlmostEqual(lat, 11.999, places=5)
        self.assertAlmostEqual(lon, 77.001, places=5)


if __name__ == "__main__":
    unittest.main()

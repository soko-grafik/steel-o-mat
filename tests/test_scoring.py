import unittest

from darts.fusion import fuse_points
from darts.runtime import RuntimeState
from darts.scoring import score_point


class ScoringTests(unittest.TestCase):
    def test_double_bull(self):
        result = score_point(0.0, 0.0)
        self.assertEqual(result.points, 50)
        self.assertEqual(result.bed, "DB")

    def test_outer_bull(self):
        result = score_point(10.0, 0.0)
        self.assertEqual(result.points, 25)
        self.assertEqual(result.bed, "OB")


class FusionTests(unittest.TestCase):
    def test_fusion_rejects_far_outlier(self):
        fused = fuse_points([(10.0, 10.0), (12.0, 10.0), (200.0, 200.0)], outlier_threshold_mm=10.0)
        self.assertIsNotNone(fused)
        assert fused is not None
        self.assertAlmostEqual(fused[0], 11.0, places=3)
        self.assertAlmostEqual(fused[1], 10.0, places=3)


class RuntimeTests(unittest.TestCase):
    def test_set_players_max_4(self):
        runtime = RuntimeState()
        runtime.set_players(["A", "B", "C", "D"], legs_to_win_set=2)
        state = runtime.snapshot()
        self.assertEqual(len(state["players"]), 4)

        with self.assertRaises(ValueError):
            runtime.set_players(["A", "B", "C", "D", "E"], legs_to_win_set=2)

    def test_history_per_dart_and_turn_exists(self):
        runtime = RuntimeState()
        runtime.set_players(["A", "B"], legs_to_win_set=2)
        runtime.set_game("501", [])

        runtime.update_from_point(0.0, 50.0, source="test")
        runtime.update_from_point(0.0, 50.0, source="test")
        runtime.update_from_point(0.0, 50.0, source="test")

        state = runtime.snapshot()
        self.assertEqual(len(state["history"]["darts"]), 3)
        self.assertEqual(len(state["history"]["turns"]), 1)
        self.assertEqual(state["history"]["turns"][0]["turn_total"], 60)

    def test_undo_restores_previous_state(self):
        runtime = RuntimeState()
        runtime.set_players(["A", "B"], legs_to_win_set=2)
        runtime.set_game("501", [])

        runtime.update_from_point(0.0, 50.0, source="test")
        state_after_throw = runtime.snapshot()
        remaining_after_throw = state_after_throw["players"][0]["remaining"]

        result = runtime.undo_last_action()
        self.assertTrue(result["ok"])

        state_after_undo = runtime.snapshot()
        self.assertGreater(state_after_undo["players"][0]["remaining"], remaining_after_throw)
        self.assertEqual(len(state_after_undo["history"]["darts"]), 0)

    def test_stats_are_exposed(self):
        runtime = RuntimeState()
        runtime.set_players(["A", "B"], legs_to_win_set=2)
        runtime.set_game("501", [])

        runtime.update_from_point(0.0, 50.0, source="test")
        runtime.update_from_point(0.0, 50.0, source="test")

        state = runtime.snapshot()
        self.assertIn("stats", state)
        self.assertIn("match", state["stats"])
        self.assertEqual(state["stats"]["match"]["total_darts"], 2)
        self.assertIn("A", state["stats"]["players"])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock
from src.leader_tracker import LeaderScheduleTracker

class TestLeaderScheduleTracker(unittest.TestCase):
    def setUp(self):
        self.mock_rpc = MagicMock()
        self.mock_rpc.get_epoch_info.return_value = {
            "epoch": 692,
            "absoluteSlot": 461310000,
            "slotIndex": 10000
        }
        self.tracker = LeaderScheduleTracker(self.mock_rpc)
        self.tracker.first_slot = 461300000
        self.tracker.leader_schedule = {
            "PubkeyA": [10, 11, 12, 13, 100, 101, 102, 103],
            "PubkeyB": [20, 21, 22, 23]
        }

    def test_get_validator_leader_slots(self):
        slots = self.tracker.get_validator_leader_slots("PubkeyA")
        self.assertEqual(slots, [461300010, 461300011, 461300012, 461300013, 461300100, 461300101, 461300102, 461300103])

    def test_upcoming_windows_grouping(self):
        windows = self.tracker.get_upcoming_windows("PubkeyA", current_slot=461300000, max_lookahead_slots=150)
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0], (461300010, 461300013))
        self.assertEqual(windows[1], (461300100, 461300103))

    def test_is_in_leader_window(self):
        self.assertTrue(self.tracker.is_in_leader_window("PubkeyB", 461300021))
        self.assertFalse(self.tracker.is_in_leader_window("PubkeyB", 461300050))

if __name__ == "__main__":
    unittest.main()

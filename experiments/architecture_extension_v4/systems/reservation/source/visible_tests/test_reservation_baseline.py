import importlib.util
import sys
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
spec = importlib.util.spec_from_file_location("v4_reservation_visible_source", SOURCE / "service.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
InMemoryCalendar, ReservationService = module.InMemoryCalendar, module.ReservationService


class ReservationBaselineTests(unittest.TestCase):
    def setUp(self):
        self.calendar = InMemoryCalendar()
        self.service = ReservationService(self.calendar)
        for room in ("amber", "blue"):
            self.service.add_room(room)

    def test_half_open_interval_and_replay(self):
        first = self.service.reserve("amber", 10, 20, "alice", "r1")
        self.assertEqual(self.service.reserve("amber", 10, 20, "alice", "r1"), first)
        self.service.reserve("amber", 20, 30, "bob", "r1")
        with self.assertRaises(ValueError):
            self.service.reserve("amber", 19, 21, "eve", "other")
        self.assertEqual(len(self.calendar.bookings), 2)

    def test_cancel_releases_capacity(self):
        booking = self.service.reserve("blue", 0, 5, "alice", "r1")
        self.service.cancel(booking.booking_id, "alice", "c1")
        self.service.cancel(booking.booking_id, "alice", "c1")
        self.service.reserve("blue", 0, 5, "bob", "r1")
        self.assertEqual(len(self.calendar.events), 3)


if __name__ == "__main__":
    unittest.main()

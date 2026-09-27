import unittest

from service import EntitlementService, InMemoryAccounts, InMemoryIssuer


class EntitlementBaselineTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryAccounts()
        self.service = EntitlementService(self.store, InMemoryIssuer())
        self.service.open_account("a", 1)
        self.service.open_account("b", 1)

    def test_seat_limit_and_account_scoped_replay(self):
        first = self.service.assign("a", "alice", "request-1")
        self.assertEqual(self.service.assign("a", "alice", "request-1"), first)
        self.service.assign("b", "bob", "request-1")
        with self.assertRaises(ValueError):
            self.service.assign("a", "bob", "request-2")
        with self.assertRaises(ValueError):
            self.service.assign("a", "other", "request-1")
        self.assertEqual(len(self.store.events), 2)

    def test_release_and_retry(self):
        self.service.assign("a", "alice", "assign-1")
        self.service.release("a", "alice", "release-1")
        self.service.release("a", "alice", "release-1")
        self.service.assign("a", "bob", "assign-2")
        self.assertEqual(set(self.store.accounts["a"].users), {"bob"})


if __name__ == "__main__":
    unittest.main()

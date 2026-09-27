"""Host-only positive control for the assessor; excluded from coding clones.

This is a protocol oracle for the small in-memory fixture, not a suggested
architecture or a scored participant. It deliberately uses the public store.
"""

from __future__ import annotations

from service import Assignment, EntitlementService, Event


class ReferenceService(EntitlementService):
    def exchange(self, account_id, departing_user_id, arriving_user_id, request_id):
        if not all((account_id, departing_user_id, arriving_user_id, request_id)):
            raise ValueError("missing identity")
        with self.store.lock:
            account = self.store.accounts[account_id]
            identity = (account_id, request_id)
            operation = ("exchange", departing_user_id, arriving_user_id)
            if identity in self.store.commands:
                previous, result = self.store.commands[identity]
                if previous != operation:
                    raise ValueError("request ID collision")
                return result
            if departing_user_id == arriving_user_id or departing_user_id not in account.users or arriving_user_id in account.users:
                raise ValueError("invalid exchange")
            result = Assignment(account_id, arriving_user_id, request_id)
            del account.users[departing_user_id]
            account.users[arriving_user_id] = result
            self.store.commands[identity] = (operation, result)
            self.store.events.append(Event("Exchanged", account_id, request_id, arriving_user_id))
            return result

    def shrink(self, account_id, new_seats, displaced_user_ids, request_id):
        if not account_id or not request_id:
            raise ValueError("missing identity")
        if type(displaced_user_ids) is not tuple:
            raise ValueError("displacements must be a tuple")
        with self.store.lock:
            account = self.store.accounts[account_id]
            identity = (account_id, request_id)
            displaced = tuple(displaced_user_ids)
            operation = ("shrink", new_seats, displaced)
            if identity in self.store.commands:
                previous, result = self.store.commands[identity]
                if previous != operation:
                    raise ValueError("request ID collision")
                return result
            if (type(new_seats) is not int or new_seats <= 0 or new_seats >= account.seats or
                len(displaced) != max(0, len(account.users) - new_seats) or
                len(set(displaced)) != len(displaced) or any(user not in account.users for user in displaced)):
                raise ValueError("invalid shrink")
            for user in displaced:
                del account.users[user]
            account.seats = new_seats
            self.store.commands[identity] = (operation, displaced)
            self.store.events.append(Event("Shrunk", account_id, request_id, ",".join(displaced)))
            return displaced

    def issue_access(self, account_id, user_id, request_id):
        if not account_id or not user_id or not request_id:
            raise ValueError("missing identity")
        with self.store.lock:
            account = self.store.accounts[account_id]
            identity = (account_id, request_id)
            operation = ("issue_access", user_id)
            if identity in self.store.commands:
                previous, result = self.store.commands[identity]
                if previous != operation:
                    raise ValueError("request ID collision")
                return result
            if user_id not in account.users:
                raise ValueError("user has no seat")

            def find():
                issued = self.issuer.lookup(account_id, request_id)
                if len(issued) > 1 or any(item.user_id != user_id for item in issued):
                    raise ValueError("issuer has conflicting outcome")
                return issued[0] if issued else None

            receipt = find()
            if receipt is None:
                try:
                    receipt = self.issuer.issue(account_id, user_id, request_id)
                except TimeoutError:
                    receipt = find()
                    if receipt is None:
                        raise
            self.store.commands[identity] = (operation, receipt)
            self.store.events.append(Event("AccessIssued", account_id, request_id, user_id))
            return receipt

"""A small seat-entitlement service. Python 3.12 standard library only.

The baseline deliberately exposes the store and issuer interfaces used by the
subsequent feature briefs. A coding episode receives one brief at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock


@dataclass(frozen=True)
class Assignment:
    account_id: str
    user_id: str
    request_id: str


@dataclass
class Account:
    seats: int
    users: dict[str, Assignment] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    name: str
    account_id: str
    request_id: str
    subject: str


class InMemoryAccounts:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.commands: dict[tuple[str, str], tuple[tuple[object, ...], object]] = {}
        self.events: list[Event] = []
        self.lock = RLock()


@dataclass(frozen=True)
class IssueReceipt:
    token_id: str
    account_id: str
    user_id: str
    request_id: str


class InMemoryIssuer:
    """An external issuer simulator; an acknowledgement is not a transaction.

    Every successful issue() call creates a new token, including calls with
    a reused request ID. A timeout may occur before an effect or after commit.
    A caller can discover a committed token with lookup(). Tests may set
    fail_before_issue or lose_next_ack before an issue call.
    """

    def __init__(self) -> None:
        self.issued: list[IssueReceipt] = []
        self.fail_before_issue = False
        self.lose_next_ack = False

    def issue(self, account_id: str, user_id: str, request_id: str) -> IssueReceipt:
        if self.fail_before_issue:
            self.fail_before_issue = False
            raise TimeoutError("issuer timed out before applying request")
        receipt = IssueReceipt(f"token-{len(self.issued) + 1}", account_id, user_id, request_id)
        self.issued.append(receipt)
        if self.lose_next_ack:
            self.lose_next_ack = False
            raise TimeoutError("issuer applied request but acknowledgement was lost")
        return receipt

    def lookup(self, account_id: str, request_id: str) -> tuple[IssueReceipt, ...]:
        return tuple(r for r in self.issued if r.account_id == account_id and r.request_id == request_id)


class EntitlementService:
    def __init__(self, store: InMemoryAccounts, issuer: InMemoryIssuer) -> None:
        self.store = store
        self.issuer = issuer

    def open_account(self, account_id: str, seats: int) -> None:
        if not account_id or type(seats) is not int or seats <= 0:
            raise ValueError("account ID and positive seat count required")
        with self.store.lock:
            if account_id in self.store.accounts:
                raise ValueError("account already exists")
            self.store.accounts[account_id] = Account(seats)

    def assign(self, account_id: str, user_id: str, request_id: str) -> Assignment:
        if not user_id or not request_id:
            raise ValueError("user ID and request ID required")
        with self.store.lock:
            account = self.store.accounts[account_id]
            command = (account_id, request_id)
            operation = ("assign", user_id)
            if command in self.store.commands:
                previous, result = self.store.commands[command]
                if previous != operation:
                    raise ValueError("request ID reused with different content")
                return result  # type: ignore[return-value]
            if user_id in account.users or len(account.users) >= account.seats:
                raise ValueError("duplicate user or account full")
            result = Assignment(account_id, user_id, request_id)
            account.users[user_id] = result
            self.store.commands[command] = (operation, result)
            self.store.events.append(Event("Assigned", account_id, request_id, user_id))
            return result

    def release(self, account_id: str, user_id: str, request_id: str) -> None:
        if not user_id or not request_id:
            raise ValueError("user ID and request ID required")
        with self.store.lock:
            account = self.store.accounts[account_id]
            command = (account_id, request_id)
            operation = ("release", user_id)
            if command in self.store.commands:
                previous, _ = self.store.commands[command]
                if previous != operation:
                    raise ValueError("request ID reused with different content")
                return
            if user_id not in account.users:
                raise ValueError("user has no seat")
            del account.users[user_id]
            self.store.commands[command] = (operation, None)
            self.store.events.append(Event("Released", account_id, request_id, user_id))

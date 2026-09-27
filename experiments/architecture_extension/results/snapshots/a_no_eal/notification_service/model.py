"""Stable application data shared by delivery channels."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    destination: str
    subject: str
    body: str


@dataclass(frozen=True)
class Payload:
    medium: str
    destination: str
    content: bytes


@dataclass(frozen=True)
class Receipt:
    medium: str
    destination: str
    content: bytes

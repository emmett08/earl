"""Mark authored support without asserting a mechanical proof."""
from __future__ import annotations

from .strategy import BuiltinStrategy


def _structured_marker(payload):
    return {'authored': True, 'mechanically_proved': False}


STRATEGY = BuiltinStrategy("structured", _structured_marker)

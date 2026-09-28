"""An immutable selection of one stateless built-in implementation.

Computational strategies return an assessment envelope. The structured strategy
returns authored-support details; its availability depends on evidence/premises
and is assessed by the common facade. Each registered schema defines the exact
contract. Keeping callbacks as module-level functions preserves code identity
checks and avoids stateful instances crossing the method registration boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class BuiltinStrategy:
    mode: str
    compute: Callable[[dict], dict]

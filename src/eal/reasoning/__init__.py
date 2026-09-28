"""Select the stateless built-in strategies; algorithms live in their modules."""
from __future__ import annotations

from .structured import STRATEGY as STRUCTURED
from .deductive import STRATEGY as DEDUCTIVE
from .inductive import STRATEGY as INDUCTIVE
from .abductive import STRATEGY as ABDUCTIVE
from .causal import STRATEGY as CAUSAL
from .counterfactual import STRATEGY as COUNTERFACTUAL
from .analogical import STRATEGY as ANALOGICAL
from .temporal import STRATEGY as TEMPORAL


BUILTIN_STRATEGIES = {
    strategy.mode: strategy for strategy in (
        STRUCTURED,
        DEDUCTIVE,
        INDUCTIVE,
        ABDUCTIVE,
        CAUSAL,
        COUNTERFACTUAL,
        ANALOGICAL,
        TEMPORAL,
    )
}

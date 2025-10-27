"""Multi-Agent AI Email System package."""

__all__ = [
    "__version__",
    "RouterAgent",
    "RoutingDecision",
    "SchedulingAgent",
    "BusinessAgent",
    "InformationAgent",
    "GeneralAgent",
]

__version__ = "0.2.0"

from .router import RouterAgent, RoutingDecision
from .experts import SchedulingAgent, BusinessAgent, InformationAgent, GeneralAgent

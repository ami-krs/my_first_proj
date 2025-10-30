"""Multi-Agent AI Email System package."""

__all__ = [
    "__version__",
    "RouterAgent",
    "RoutingDecision",
    "SchedulingAgent",
    "BusinessAgent",
    "InformationAgent",
    "GeneralAgent",
    "EmailReporter",
    "log_email_event",
]

__version__ = "0.3.0"

from .router import RouterAgent, RoutingDecision
from .experts import SchedulingAgent, BusinessAgent, InformationAgent, GeneralAgent
from .reporter import EmailReporter, log_email_event

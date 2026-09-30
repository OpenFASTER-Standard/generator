from dataclasses import dataclass
from enum import Enum
from typing import Any


class Status(Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    UNCITABLE = "UNCITABLE"


@dataclass(frozen=True)
class ResolutionOutcome:
    status: Status
    raw_content: Any = None

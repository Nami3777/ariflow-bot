from dataclasses import dataclass, field
from typing import Literal

OperatorStatus = Literal["active", "sick", "umi", "unassigned"]


@dataclass
class Operator:
    station: str
    station_type: str
    shift_start: str
    shift_end: str
    umi_start: str
    umi_end: str
    umi_sop: str        # plain number, e.g. "6"
    sop1: str           # "SOP#00033(90)"
    sop2: str
    sop3: str
    sop4: str
    status: OperatorStatus = "active"


@dataclass
class SickReallocation:
    absent: str
    replacement: str
    station: str
    station_type: str
    timestamp: str


@dataclass
class AckRecord:
    name: str
    timestamp: str


class ShiftState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.schedule_loaded: bool = False
        self.shift_date: str = ""
        self.operators: dict[str, Operator] = {}
        self.sick_reallocations: list[SickReallocation] = []
        self.ack_records: dict[str, AckRecord] = {}
        self.ack_version: int = 0
        self.pending_acks: set[str] = set()
        self.announcements: list[str] = []
        self.umi_covers: dict[str, str] = {}  # operator_name → cover_name

    def get_unassigned(self) -> list[str]:
        return [
            name for name, op in self.operators.items()
            if op.status == "unassigned"
        ]

    def summary(self) -> str:
        if not self.schedule_loaded:
            return "No schedule loaded."
        gaps = [r for r in self.sick_reallocations if r.replacement == "UNCOVERED"]
        lines = [
            f"Schedule: {self.shift_date}",
            f"Operators: {len(self.operators)}",
            f"Sick reallocations: {len(self.sick_reallocations)}",
            f"Coverage gaps: {len(gaps)}",
        ]
        if self.announcements:
            lines.append(f"Announcements ({len(self.announcements)}):")
            for i, a in enumerate(self.announcements, start=1):
                lines.append(f"  {i}. {a}")
        return "\n".join(lines)


# Global singleton
state = ShiftState()

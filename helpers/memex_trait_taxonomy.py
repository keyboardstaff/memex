from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class TraitCategory(Enum):
    COMMUNICATION = "communication"
    TECHNICAL = "technical"
    WORKFLOW = "workflow"
    PERSONALITY = "personality"
    DOMAIN = "domain"


class ConfidenceLevel(Enum):
    HYPOTHESIS = "hypothesis"       # 0.0-0.3
    EMERGING = "emerging"           # 0.3-0.6
    ESTABLISHED = "established"     # 0.6-0.8
    STRONG = "strong"               # 0.8-1.0


@dataclass
class TraitObservation:
    content: str
    context_id: str
    timestamp: str
    signal_strength: float = 0.5


@dataclass
class UserTrait:
    id: str
    category: TraitCategory
    name: str

    thesis: str
    antithesis: Optional[str] = None
    synthesis: Optional[str] = None

    confidence: float = 0.3
    observations: list[TraitObservation] = field(default_factory=list)
    last_updated: str = ""

    conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "name": self.name,
            "thesis": self.thesis,
            "antithesis": self.antithesis,
            "synthesis": self.synthesis,
            "confidence": self.confidence,
            "observations": [
                {"content": o.content, "context_id": o.context_id,
                 "timestamp": o.timestamp, "signal_strength": o.signal_strength}
                for o in self.observations
            ],
            "last_updated": self.last_updated,
            "conditions": self.conditions,
        }

    @staticmethod
    def from_dict(data: dict) -> "UserTrait":
        return UserTrait(
            id=data["id"],
            category=TraitCategory(data.get("category", "communication")),
            name=data["name"],
            thesis=data.get("thesis", ""),
            antithesis=data.get("antithesis"),
            synthesis=data.get("synthesis"),
            confidence=data.get("confidence", 0.3),
            observations=[
                TraitObservation(**o) for o in data.get("observations", [])
            ],
            last_updated=data.get("last_updated", ""),
            conditions=data.get("conditions", []),
        )

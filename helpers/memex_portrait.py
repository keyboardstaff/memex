import json
import os
from dataclasses import dataclass, field
from helpers import files
from usr.plugins.memex.helpers.memex_trait_taxonomy import (
    TraitCategory, UserTrait,
)

DATA_PATH = "usr/plugins/memex/data/portrait.json"


@dataclass
class Portrait:
    user_id: str = "default"
    traits: dict[str, UserTrait] = field(default_factory=dict)
    last_updated: str = ""
    version: int = 0

    def get_traits_by_category(self, category: TraitCategory) -> list[UserTrait]:
        return [t for t in self.traits.values() if t.category == category]

    def get_established_traits(self) -> list[UserTrait]:
        return [t for t in self.traits.values() if t.confidence >= 0.6]

    def get_actionable_summary(self) -> str:
        lines = []
        for trait in sorted(self.traits.values(), key=lambda t: -t.confidence):
            if trait.confidence < 0.3:
                continue
            description = trait.synthesis or trait.thesis
            if trait.conditions:
                conditions_str = ", ".join(trait.conditions)
                lines.append(f"- {description} (when: {conditions_str})")
            else:
                lines.append(f"- {description}")
        return "\n".join(lines) if lines else ""

    def get_relevant_traits(self, query: str, min_confidence: float = 0.5) -> str:
        query_lower = query.lower()
        relevant = []
        for trait in self.traits.values():
            if trait.confidence < min_confidence:
                continue
            name_words = trait.name.lower().replace("_", " ").split()
            if any(w in query_lower for w in name_words):
                desc = trait.synthesis or trait.thesis
                if trait.conditions:
                    desc += f" (when: {', '.join(trait.conditions)})"
                relevant.append(f"- {desc}")
        return "\n".join(relevant) if relevant else ""

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "traits": {k: v.to_dict() for k, v in self.traits.items()},
            "last_updated": self.last_updated,
            "version": self.version,
        }

    @staticmethod
    def from_dict(data: dict) -> "Portrait":
        traits = {}
        for k, v in data.get("traits", {}).items():
            traits[k] = UserTrait.from_dict(v)
        return Portrait(
            user_id=data.get("user_id", "default"),
            traits=traits,
            last_updated=data.get("last_updated", ""),
            version=data.get("version", 0),
        )


def load_portrait() -> Portrait:
    path = files.get_abs_path(DATA_PATH)
    if os.path.exists(path):
        try:
            data = json.loads(files.read_file(DATA_PATH))
            return Portrait.from_dict(data)
        except Exception:
            pass
    return Portrait()


def save_portrait(portrait: Portrait):
    files.write_file(DATA_PATH, json.dumps(portrait.to_dict(), ensure_ascii=False, indent=2))

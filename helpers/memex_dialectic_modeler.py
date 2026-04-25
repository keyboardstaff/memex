import json
from datetime import datetime, timezone
from typing import Optional
from helpers.dirty_json import DirtyJson

from usr.plugins.memex.helpers.memex_portrait import Portrait, load_portrait, save_portrait
from usr.plugins.memex.helpers.memex_trait_taxonomy import (
    TraitCategory, UserTrait, TraitObservation,
)


class DialecticModeler:

    def __init__(self, agent=None):
        self.agent = agent
        self.model = load_portrait()

    async def update_from_conversation(self, context_id: str, messages: list):
        observations = await self._extract_observations(messages, context_id)
        if not observations:
            return

        for obs in observations:
            await self._dialectic_integrate(obs, context_id)

        self.model.version += 1
        self.model.last_updated = datetime.now(timezone.utc).isoformat()
        save_portrait(self.model)

    async def _extract_observations(self, messages: list, context_id: str) -> list[dict]:
        if not self.agent:
            return []

        msgs_text = "\n".join(
            f"[{'agent' if m.get('ai') else 'user'}]: {str(m.get('content', ''))[:500]}"
            for m in messages[-20:]
        )

        max_obs = 5
        if hasattr(self.agent, "config"):
            from helpers import plugins
            config = plugins.get_plugin_config("memex", self.agent)
            if config:
                max_obs = config.get("portrait_max_observations", 5)

        system = self.agent.read_prompt(
            "portrait.update.sys.md",
            max_observations=max_obs,
        )
        message = self.agent.read_prompt(
            "portrait.update.msg.md",
            conversation=msgs_text,
            existing_traits=self.model.get_actionable_summary() or "None yet.",
        )

        response = await self.agent.call_utility_model(
            system=system,
            message=message,
            background=True,
        )

        try:
            result = DirtyJson.parse_string(response.strip())
            return result if isinstance(result, list) else []
        except Exception:
            return []

    async def _dialectic_integrate(self, observation: dict, context_id: str = ""):
        trait_name = observation.get("trait_name", "")
        new_evidence = observation.get("evidence", "")
        category = observation.get("category", "communication")

        if not trait_name or not new_evidence:
            return

        existing = self._find_matching_trait(trait_name, category)
        now = datetime.now(timezone.utc).isoformat()
        obs = TraitObservation(
            content=new_evidence,
            context_id=context_id,
            timestamp=now,
            signal_strength=observation.get("strength", 0.5),
        )

        if existing is None:
            trait = UserTrait(
                id=f"trait_{len(self.model.traits)}",
                category=TraitCategory(category),
                name=trait_name,
                thesis=new_evidence,
                confidence=0.3,
                observations=[obs],
                last_updated=now,
            )
            self.model.traits[trait.id] = trait

        elif self._is_contradicting(existing.thesis, new_evidence):
            existing.antithesis = new_evidence
            existing.observations.append(obs)
            existing.last_updated = now

            synthesis = await self._synthesize(existing)
            if synthesis:
                existing.synthesis = synthesis.get("synthesis", "")
                existing.conditions = synthesis.get("conditions", [])
                existing.confidence = min(0.9, existing.confidence + 0.1)
        else:
            existing.observations.append(obs)
            existing.confidence = min(1.0, existing.confidence + 0.15)
            existing.last_updated = now

    def _is_contradicting(self, thesis: str, new_evidence: str) -> bool:
        contradiction_signals = [
            ("detailed", "concise"), ("verbose", "brief"),
            ("formal", "casual"), ("prefer", "avoid"),
            ("always", "never"), ("more", "less"),
        ]
        thesis_lower = thesis.lower()
        evidence_lower = new_evidence.lower()
        for a, b in contradiction_signals:
            if (a in thesis_lower and b in evidence_lower) or \
               (b in thesis_lower and a in evidence_lower):
                return True
        return False

    async def _synthesize(self, trait: UserTrait) -> Optional[dict]:
        if not self.agent:
            return None

        system = self.agent.read_prompt("portrait.dialectic.sys.md")
        message = self.agent.read_prompt(
            "portrait.dialectic.msg.md",
            trait_name=trait.name,
            thesis=trait.thesis,
            antithesis=trait.antithesis or "",
            observations=json.dumps(
                [o.content for o in trait.observations[-5:]],
                ensure_ascii=False,
            ),
        )

        response = await self.agent.call_utility_model(
            system=system,
            message=message,
            background=True,
        )

        try:
            result = DirtyJson.parse_string(response.strip())
            return result if isinstance(result, dict) else None
        except Exception:
            return None

    def _find_matching_trait(self, name: str, category: str) -> Optional[UserTrait]:
        name_lower = name.lower().replace("_", " ")
        for trait in self.model.traits.values():
            if trait.name.lower().replace("_", " ") == name_lower:
                return trait
            if trait.category.value == category and \
               any(word in trait.name.lower() for word in name_lower.split() if len(word) > 2):
                return trait
        return None

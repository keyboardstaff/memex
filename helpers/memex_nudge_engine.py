import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from helpers import files
from helpers.print_style import PrintStyle

_STATE_PATH = "usr/plugins/memex/data/nudge.json"


@dataclass
class NudgeConfig:
    interval_minutes: int = 60
    batch_size: int = 8
    min_age_hours: int = 48
    insight_threshold: int = 3
    archive_score_threshold: float = 0.05
    max_llm_calls_per_cycle: int = 3
    max_insights_total: int = 500


@dataclass
class NudgeResult:
    reviewed: int = 0
    insights_created: int = 0
    archived: int = 0
    errors: list = field(default_factory=list)


def _load_state() -> dict:
    path = files.get_abs_path(_STATE_PATH)
    if files.exists(path):
        try:
            return json.loads(files.read_file(path))
        except Exception:
            pass
    return {
        "last_nudge_time": None,
        "cursor": {},
        "insights_generated": 0,
        "memories_archived": 0,
        "last_error": None,
    }


def _save_state(state: dict):
    path = files.get_abs_path(_STATE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    files.write_file(path, json.dumps(state, indent=2, default=str))


class NudgeEngine:

    def __init__(self, config: NudgeConfig):
        self.config = config
        self.state = _load_state()

    async def run_cycle(self, agent, memory_subdir: str) -> NudgeResult:
        """Execute one review cycle for memory_subdir."""
        result = NudgeResult()

        try:
            from plugins._memory.helpers.memory import Memory

            db = await Memory.get_by_subdir(memory_subdir, preload_knowledge=False)
            all_docs = db.db.get_all_docs()

            if not all_docs:
                return result

            candidates = self._get_review_candidates(all_docs, memory_subdir)
            batch = candidates[: self.config.batch_size]

            llm_calls = 0
            for doc_id, doc in batch:
                if llm_calls >= self.config.max_llm_calls_per_cycle:
                    break
                review = await self._review_single_memory(agent, doc)
                llm_calls += 1
                result.reviewed += 1

                if review.get("should_archive"):
                    result.archived += 1
                    self.state["memories_archived"] = self.state.get("memories_archived", 0) + 1
                    subdir_cursor = self.state.setdefault("cursor", {}).setdefault(memory_subdir, {})
                    subdir_cursor["memories_archived"] = subdir_cursor.get("memories_archived", 0) + 1

                importance_adj = review.get("importance_adjustment", 0)
                if importance_adj != 0:
                    await self._update_importance(doc_id, memory_subdir, importance_adj)

            if result.reviewed >= self.config.insight_threshold:
                insights = await self._extract_insights(agent, batch, memory_subdir)
                result.insights_created = len(insights)
                llm_calls += 1

                for insight in insights:
                    await self._store_insight(db, insight, memory_subdir)

            self._update_cursor(memory_subdir, batch)
            self.state["last_nudge_time"] = datetime.now(timezone.utc).isoformat()
            _save_state(self.state)

        except Exception as e:
            result.errors.append(str(e))
            self.state["last_error"] = str(e)
            _save_state(self.state)

        return result

    def _get_review_candidates(self, all_docs: dict, subdir: str) -> list:
        now = datetime.now(timezone.utc)
        min_age_secs = self.config.min_age_hours * 3600

        cursor_info = self.state.get("cursor", {}).get(subdir, {})
        last_reviewed_id = cursor_info.get("last_reviewed_id", "")

        candidates = []
        past_cursor = not bool(last_reviewed_id)

        for doc_id, doc in all_docs.items():
            if not past_cursor:
                if doc_id == last_reviewed_id:
                    past_cursor = True
                continue

            ts = doc.metadata.get("timestamp", "")
            if ts:
                try:
                    created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    age = (now - created).total_seconds()
                    if age < min_age_secs:
                        continue
                except (ValueError, TypeError):
                    pass

            candidates.append((doc_id, doc))

        # Wrap around
        if not candidates and last_reviewed_id:
            cursor_info["last_reviewed_id"] = ""
            cursor_info["cycle_count"] = cursor_info.get("cycle_count", 0) + 1
            self.state.setdefault("cursor", {})[subdir] = cursor_info
            return self._get_review_candidates(all_docs, subdir)

        return candidates

    async def _review_single_memory(self, agent, doc) -> dict:
        from helpers.dirty_json import DirtyJson

        content = doc.page_content
        metadata = doc.metadata

        system = agent.read_prompt("nudge.review.sys.md")
        message = agent.read_prompt(
            "nudge.review.msg.md",
            memory_content=content,
            memory_id=metadata.get("id", ""),
            memory_timestamp=metadata.get("timestamp", "unknown"),
            memory_area=metadata.get("area", "main"),
        )

        response = await agent.call_utility_model(
            system=system,
            message=message,
            background=True,
        )

        try:
            return DirtyJson.parse_string(response.strip())
        except Exception:
            return {"still_relevant": True, "should_archive": False}

    async def _extract_insights(self, agent, batch: list, subdir: str) -> list:
        from helpers.dirty_json import DirtyJson

        memories_text = "\n\n".join(
            f"[{doc.metadata.get('id', i)}]: {doc.page_content[:500]}"
            for i, (doc_id, doc) in enumerate(batch)
        )

        system = agent.read_prompt("nudge.insight.sys.md")
        message = agent.read_prompt(
            "nudge.insight.msg.md",
            memories=memories_text,
            memory_subdir=subdir,
        )

        response = await agent.call_utility_model(
            system=system,
            message=message,
            background=True,
        )

        try:
            result = DirtyJson.parse_string(response.strip())
            if not isinstance(result, list):
                return []
            return result[:3]  # Fix hard cap per call
        except Exception:
            return []

    async def _store_insight(self, db, insight: dict, subdir: str):
        text = insight.get("insight", "")
        if not text:
            return

        # Proposal A: global cap
        if self.config.max_insights_total > 0 and self.state.get("insights_generated", 0) >= self.config.max_insights_total:
            return

        category = insight.get("category", "pattern")
        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "source": "nudge",
            "category": category,
            "confidence": insight.get("confidence", 0.5),
            "timestamp": now,
            "area": "fragments",
        }

        await db.insert_text(text, metadata)
        self.state["insights_generated"] = self.state.get("insights_generated", 0) + 1
        # Per-subdir
        subdir_cursor = self.state.setdefault("cursor", {}).setdefault(subdir, {})
        subdir_cursor["insights_generated"] = subdir_cursor.get("insights_generated", 0) + 1

    async def _update_importance(self, doc_id: str, subdir: str, adjustment: float):
        pass

    def _update_cursor(self, subdir: str, batch: list):
        if not batch:
            return
        last_id = batch[-1][0]
        cursor = self.state.setdefault("cursor", {}).setdefault(subdir, {})
        cursor["last_reviewed_id"] = last_id
        cursor["total_reviewed"] = cursor.get("total_reviewed", 0) + len(batch)

import logging
from helpers.extension import Extension
from helpers import plugins
from helpers.history import output_text
from agent import Agent, LoopData

_log = logging.getLogger(__name__)

# Counter save key
_DATA_SAVED_COUNTER = "_memex_chapter_saved_counter"


class AutoCompactCheck(Extension):
    """Snapshot conversation history into a chapter before A0 compresses it."""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        # Root agent only
        if self.agent.data.get(Agent.DATA_NAME_SUPERIOR):
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("auto_compact_enabled", True):
            return

        history = self.agent.history

        # Check limit
        try:
            over = history.is_over_limit()
        except Exception:
            return  # _model_config may not be available yet

        current_counter = history.counter

        if not over:
            # Reset guard on counter rollback
            saved_counter = self.agent.get_data(_DATA_SAVED_COUNTER)
            if saved_counter and current_counter < saved_counter:
                self.agent.set_data(_DATA_SAVED_COUNTER, 0)
            return

        # Cooldown guard
        min_new = config.get("auto_compact_min_new_messages", 10)
        saved_counter = self.agent.get_data(_DATA_SAVED_COUNTER) or 0

        # Counter rollback
        if current_counter < saved_counter:
            saved_counter = 0
            self.agent.set_data(_DATA_SAVED_COUNTER, 0)

        new_since_save = current_counter - saved_counter
        if new_since_save < min_new:
            return

        # Snapshot
        try:
            from helpers import tokens as tokens_helper
            from helpers import projects

            history_output = history.output()
            full_text      = output_text(history_output, ai_label="AI", human_label="User")
            if not full_text.strip():
                return

            token_count    = tokens_helper.approximate_tokens(full_text)
            message_count  = current_counter
            project_name   = projects.get_context_project_name(self.agent.context) or ""

            from usr.plugins.memex.helpers.memex_chapters import save_chapter
            chapter_id = save_chapter(
                context_id    = self.agent.context.id,
                project_name  = project_name,
                history_text  = full_text,
                token_count   = token_count,
                message_count = message_count,
            )

            # Update guard
            self.agent.set_data(_DATA_SAVED_COUNTER, current_counter)

            _log.info(
                "Memex: chapter snapshot saved (id=%s, tokens=%d, msgs=%d)",
                chapter_id[:8], token_count, message_count,
            )

            # Extract and persist key facts before compression (Proposal B)
            if config.get("auto_compact_save_facts", True):
                max_facts = config.get("auto_compact_max_facts", 5)
                await _save_compression_facts(self.agent, full_text, max_facts)

        except Exception as e:
            _log.warning("Memex auto_compact_check failed: %s", e)


async def _save_compression_facts(agent, text: str, max_facts: int) -> None:
    """Extract key facts from conversation text and persist to memory before compression."""
    try:
        from helpers.dirty_json import DirtyJson
        from plugins._memory.helpers.memory import Memory

        system = agent.read_prompt("compact.facts.sys.md")
        if not system:
            return

        response = await agent.call_utility_model(
            system=system,
            message=text[-4000:],
            background=True,
        )
        if not response:
            return

        facts = DirtyJson.parse_string(response.strip())
        if not isinstance(facts, list):
            return

        memory = await Memory.get(agent)
        for item in facts[:max_facts]:
            fact_text = item.get("fact", "").strip() if isinstance(item, dict) else str(item).strip()
            if fact_text:
                await memory.insert_text(fact_text, {"source": "compact_facts", "area": "main"})

    except Exception as e:
        _log.warning("Memex compact facts extraction failed: %s", e)

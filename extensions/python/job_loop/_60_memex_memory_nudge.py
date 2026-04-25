import time
from helpers.extension import Extension
from helpers import plugins
from helpers.defer import DeferredTask, THREAD_BACKGROUND
from helpers.print_style import PrintStyle

_last_nudge_time = 0
_nudge_running = False
_monologue_counter: dict[str, int] = {}

_NUDGE_CONTEXT_ID = "__memex_nudge__"


class MemoryNudge(Extension):
    """Periodically review old memories in the background (time + turn hybrid trigger)."""

    async def execute(self, **kwargs):
        global _last_nudge_time, _nudge_running

        if _nudge_running:
            return

        config = plugins.get_plugin_config("memex")
        if not config or not config.get("nudge_enabled", True):
            return

        interval = config.get("nudge_interval_minutes", 60) * 60
        turn_interval = config.get("nudge_turn_interval", 10)
        now = time.time()

        time_triggered = (now - _last_nudge_time >= interval)

        turn_triggered = False
        for ctx_id, count in _monologue_counter.items():
            if count >= turn_interval:
                turn_triggered = True
                break

        if not time_triggered and not turn_triggered:
            return

        _last_nudge_time = now
        _nudge_running = True
        _monologue_counter.clear()

        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(self._run_nudge, config)

    @staticmethod
    def increment_turn(context_id: str):
        """Called by monologue_end extensions to accumulate turn count."""
        _monologue_counter[context_id] = _monologue_counter.get(context_id, 0) + 1

    @staticmethod
    async def _run_nudge(config: dict):
        global _nudge_running
        try:
            from initialize import initialize_agent
            from agent import AgentContext, AgentContextType
            from usr.plugins.memex.helpers.memex_nudge_engine import NudgeEngine, NudgeConfig
            from plugins._memory.helpers.memory import get_existing_memory_subdirs

            # Create a temporary context for LLM calls
            agent_config = initialize_agent()
            context = AgentContext(
                agent_config,
                id=_NUDGE_CONTEXT_ID,
                name="memex-nudge",
                type=AgentContextType.BACKGROUND,
            )
            agent = context.agent0

            engine = NudgeEngine(NudgeConfig(
                interval_minutes=config.get("nudge_interval_minutes", 60),
                batch_size=config.get("nudge_batch_size", 8),
                min_age_hours=config.get("nudge_min_age_hours", 48),
                insight_threshold=config.get("nudge_insight_threshold", 5),
                archive_score_threshold=config.get("nudge_archive_score_threshold", 0.05),
                max_llm_calls_per_cycle=config.get("nudge_max_llm_calls", 3),
                max_insights_total=config.get("nudge_max_insights_total", 500),
            ))

            for subdir in get_existing_memory_subdirs():
                result = await engine.run_cycle(agent, subdir)
                PrintStyle.standard(
                    f"[Nudge] {subdir}: reviewed={result.reviewed}, "
                    f"insights={result.insights_created}, archived={result.archived}"
                )

            # Clean up temporary context
            AgentContext.remove(_NUDGE_CONTEXT_ID)

        except Exception as e:
            PrintStyle.error(f"[Nudge] Error: {e}")
        finally:
            _nudge_running = False

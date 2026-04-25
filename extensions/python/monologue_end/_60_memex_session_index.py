from helpers.extension import Extension
from helpers import plugins, projects
from helpers.defer import DeferredTask, THREAD_BACKGROUND
from helpers.print_style import PrintStyle
from agent import LoopData


class SessionIndexExt(Extension):

    def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        # Nudge counter
        try:
            from usr.plugins.memex.extensions.python.job_loop._60_memex_memory_nudge import MemoryNudge
            MemoryNudge.increment_turn(self.agent.context.id)
        except Exception:
            pass

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("session_search_enabled", True):
            return

        min_msgs = config.get("session_index_min_messages", 3)
        msgs = self.agent.history.current.messages
        if len(msgs) < min_msgs:
            return

        context = self.agent.context
        messages = [m.to_dict() for m in msgs]
        project_name = projects.get_context_project_name(context) or ""
        agent_name = self.agent.agent_name

        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(
            self._index_session,
            context.id,
            messages,
            project_name,
            agent_name,
        )

    @staticmethod
    async def _index_session(ctx_id, messages, project, agent_name):
        try:
            from usr.plugins.memex.helpers.memex_session_index import SessionIndex

            index = SessionIndex()
            indexed = index.index_conversation(ctx_id, messages, project, agent_name)
            if indexed:
                PrintStyle.standard(
                    f"[SessionSearch] Indexed {len(messages)} messages for {ctx_id[:8]}"
                )
        except Exception as e:
            PrintStyle.error(f"[SessionSearch] Index error: {e}")

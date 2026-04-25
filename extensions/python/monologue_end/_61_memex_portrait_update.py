from helpers.extension import Extension
from helpers import plugins
from helpers.defer import DeferredTask, THREAD_BACKGROUND
from agent import LoopData


class PortraitUpdate(Extension):

    def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("portrait_enabled", True):
            return

        min_msgs = config.get("portrait_min_messages", 4)
        msgs = self.agent.history.current.messages
        if len(msgs) < min_msgs:
            return

        context_id = self.agent.context.id
        messages = [m.to_dict() for m in msgs]

        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(self._update_portrait, context_id, messages)

    @staticmethod
    async def _update_portrait(context_id, messages):
        try:
            import initialize
            from agent import AgentContext, AgentContextType

            config = initialize.initialize_agent()
            context = AgentContext(
                config=config,
                id="__memex_portrait__",
                name="Memex Portrait",
                type=AgentContextType.BACKGROUND,
            )
            agent = context.agent0

            from usr.plugins.memex.helpers.memex_dialectic_modeler import DialecticModeler
            modeler = DialecticModeler(agent)
            await modeler.update_from_conversation(context_id, messages)

            AgentContext.remove("__memex_portrait__")
        except Exception:
            pass

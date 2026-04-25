from helpers.extension import Extension
from helpers import plugins
from agent import LoopData


class PortraitInject(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("portrait_enabled", True):
            return

        if loop_data.iteration > 2:
            return

        user_msg = loop_data.user_message.output_text() if loop_data.user_message else ""
        if not user_msg or len(user_msg) < 10:
            return

        from usr.plugins.memex.helpers.memex_portrait import load_portrait

        portrait = load_portrait()
        min_conf = config.get("portrait_inject_min_confidence", 0.5)
        relevant = portrait.get_relevant_traits(user_msg, min_confidence=min_conf)
        if not relevant:
            return

        extras = loop_data.extras_temporary
        extras["user_preferences"] = self.agent.read_prompt(
            "portrait.inject.msg.md",
            relevant_traits=relevant,
        )

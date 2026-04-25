from helpers.extension import Extension
from helpers import plugins
from agent import LoopData


class PortraitPrompt(Extension):

    async def execute(self, system_prompt: list[str] = [], loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("portrait_enabled", True):
            return

        from usr.plugins.memex.helpers.memex_portrait import load_portrait

        portrait = load_portrait()
        summary = portrait.get_actionable_summary()
        if not summary:
            return

        prompt = self.agent.read_prompt(
            "portrait.inject.sys.md",
            user_preferences=summary,
        )
        system_prompt.append(prompt)

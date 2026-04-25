from helpers.extension import Extension
from helpers import plugins
from agent import LoopData


class DecayRerank(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("decay_enabled", True):
            return

        extras = loop_data.extras_persistent
        if "memories" not in extras:
            return

        from usr.plugins.memex.helpers.memex_decay import rerank_memories

        extras["memories"] = await rerank_memories(
            self.agent, extras["memories"], config
        )

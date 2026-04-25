from helpers.extension import Extension
from helpers import plugins
from tools.skills_tool import DATA_NAME_LOADED_SKILLS


class CapLoadedSkills(Extension):
    """Enforce skills_max_loaded rolling window after skills_tool:load."""

    async def execute(self, tool_name: str = "", **kwargs):
        if tool_name != "skills_tool" or not self.agent:
            return
        config = plugins.get_plugin_config("memex", self.agent)
        if not config:
            return
        try:
            cap = int(config.get("skills_max_loaded", 5))
        except (TypeError, ValueError):
            return
        if cap <= 0:
            return
        loaded = self.agent.data.get(DATA_NAME_LOADED_SKILLS)
        if isinstance(loaded, list) and len(loaded) > cap:
            self.agent.data[DATA_NAME_LOADED_SKILLS] = loaded[-cap:]

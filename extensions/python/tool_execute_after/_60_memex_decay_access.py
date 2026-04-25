from helpers.extension import Extension
from helpers.tool import Response
from helpers import plugins


class DecayAccess(Extension):

    async def execute(self, tool_name: str = "", response: Response | None = None, **kwargs):
        if not self.agent or not response:
            return
        if tool_name != "memory_load":
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("decay_enabled", True):
            return

        from usr.plugins.memex.helpers.memex_decay import extract_memory_ids_from_text, record_access

        ids = extract_memory_ids_from_text(response.message)
        if not ids:
            return

        from plugins._memory.helpers.memory import Memory
        db = await Memory.get(self.agent)
        subdir = db.memory_subdir if hasattr(db, "memory_subdir") else "default"
        record_access(ids, subdir)

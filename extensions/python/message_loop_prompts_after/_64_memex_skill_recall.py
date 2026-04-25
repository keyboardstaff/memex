from helpers.extension import Extension
from helpers import plugins
from agent import LoopData


class MemexSkillsIndex(Extension):
    """Inject a compact memex skills index into the system prompt every turn."""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return
        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("skills_enabled", True):
            return
        index_all = config.get("skills_index_all", False)
        try:
            from helpers.skills import list_skills
            all_skills = list_skills(self.agent)
            skills = all_skills if index_all else [
                s for s in all_skills if "memex-auto" in s.tags
            ]
        except Exception:
            return
        if not skills:
            return
        lines = "\n".join(
            f"  - {s.name}" + (f": {s.description[:80]}" if s.description else "")
            for s in sorted(skills, key=lambda x: x.name)
        )
        block = self.agent.read_prompt("skills.index.md", index=lines)
        loop_data.system.append(block)

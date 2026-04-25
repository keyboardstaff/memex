import os
from helpers.extension import Extension
from helpers import plugins
from helpers.defer import DeferredTask, THREAD_BACKGROUND
from helpers.print_style import PrintStyle
from agent import LoopData

# skill_name -> usage count at last improvement (prevents re-review same checkpoint)
_last_improved: dict[str, int] = {}


class SkillImprove(Extension):
    """Review heavily-used memex-auto skills and propose improvements."""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config:
            return
        if not config.get("skills_improve_enabled", True):
            return
        if not config.get("skills_enabled", True):
            return

        threshold = config.get("skills_improve_threshold", 5)

        from usr.plugins.memex.helpers.memex_skill_usage import get_counts
        counts = get_counts()

        # Candidates: count is a nonzero multiple of threshold not yet improved
        candidates = [
            (name, cnt) for name, cnt in counts.items()
            if cnt > 0 and cnt % threshold == 0 and _last_improved.get(name, 0) < cnt
        ]
        if not candidates:
            return

        msgs = self.agent.history.current.messages
        if not msgs:
            return
        conversation = "\n".join(
            f"{'AI' if m.ai else 'User'}: {m.output_text()[:300]}"
            for m in msgs[-10:]
        )

        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(
            self._improve_skills,
            self.agent,
            candidates[:2],  # at most 2 per monologue
            conversation,
        )

    @staticmethod
    async def _improve_skills(agent, candidates: list, conversation: str):
        try:
            from helpers import files
            from helpers.dirty_json import DirtyJson
            from usr.plugins.memex.helpers.memex_skill_index import SkillIndex

            try:
                import yaml as pyyaml
            except Exception:
                pyyaml = None

            index = SkillIndex()
            skill_root = SkillIndex._resolve_skill_root(agent)
            system = agent.read_prompt("skills.improve.sys.md")
            if not system:
                return

            for skill_name, count in candidates:
                skill_path = os.path.join(skill_root, skill_name, "SKILL.md")
                if not os.path.isfile(skill_path):
                    continue

                current_content = files.read_file(skill_path)

                # Only improve memex-auto skills
                if pyyaml:
                    try:
                        end = current_content.index("---", 3)
                        fm = pyyaml.safe_load(current_content[3:end]) or {}
                        if "memex-auto" not in fm.get("tags", []):
                            continue
                    except Exception:
                        continue

                msg = (
                    f"Skill name: {skill_name}\n"
                    f"Usage count: {count}\n\n"
                    f"Current SKILL.md:\n{current_content}\n\n"
                    f"Recent conversation context:\n{conversation}"
                )

                response = await agent.call_utility_model(
                    system=system,
                    message=msg,
                    background=True,
                )
                if not response:
                    continue

                result = DirtyJson.parse_string(response)
                if not isinstance(result, dict) or not result.get("improve"):
                    _last_improved[skill_name] = count
                    continue

                new_content = result.get("content", "").strip()
                if not new_content:
                    continue

                triggers = result.get("triggers", [])
                tags = result.get("tags", ["memex-auto"])
                title = result.get("title", skill_name)

                if not isinstance(triggers, list):
                    triggers = []
                if not isinstance(tags, list):
                    tags = ["memex-auto"]

                index.save_skill(skill_name, title, new_content, triggers, tags, agent=agent)
                _last_improved[skill_name] = count

                PrintStyle(font_color="#1B4F72", padding=True).print(
                    f"[Memex Skill Improve] Updated: {skill_name} (used {count}x)"
                )

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Memex Skill Improve] Error: {e}")

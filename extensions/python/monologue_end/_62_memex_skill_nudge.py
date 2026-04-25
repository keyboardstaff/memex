from helpers.extension import Extension
from helpers import plugins
from helpers.defer import DeferredTask, THREAD_BACKGROUND
from helpers.print_style import PrintStyle
from agent import LoopData

# Track skills created per conversation to enforce limit
_skills_created: dict[str, int] = {}


class SkillNudge(Extension):
    """Check if a memex skill should be created/updated after conversation ends."""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("skills_enabled", True):
            return

        # Iteration threshold
        min_iterations = config.get("skills_min_tool_iterations", 5)
        if loop_data.iteration < min_iterations:
            return

        # Per-conv limit
        max_per_conv = config.get("skills_max_per_conversation", 2)
        ctx_id = self.agent.context.id
        created = _skills_created.get(ctx_id, 0)
        if created >= max_per_conv:
            return

        # Build context
        msgs = self.agent.history.current.messages
        if not msgs:
            return
        conversation = "\n".join(
            f"{'AI' if m.ai else 'User'}: {m.output_text()[:500]}"
            for m in msgs[-20:]
        )

        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(
            self._review_for_skills,
            self.agent,
            config,
            conversation,
            ctx_id,
        )

    @staticmethod
    async def _review_for_skills(agent, config, conversation, ctx_id):
        try:
            system = agent.read_prompt("skills.nudge.sys.md")
            if not system:
                return

            from usr.plugins.memex.helpers.memex_skill_index import SkillIndex
            from helpers.dirty_json import DirtyJson

            index = SkillIndex()

            # Existing skills
            try:
                from helpers.skills import list_skills
                import datetime
                _now = datetime.datetime.now(tz=datetime.timezone.utc)
                _all = list_skills(agent, include_content=True)
                existing_names = []
                for s in _all:
                    if "memex-auto" not in s.tags:
                        continue
                    _exp = s.raw_frontmatter.get("expires")
                    if _exp:
                        try:
                            _exp_dt = datetime.datetime.fromisoformat(str(_exp))
                            if _exp_dt.tzinfo is None:
                                _exp_dt = _exp_dt.replace(tzinfo=datetime.timezone.utc)
                            if _exp_dt < _now:
                                continue  # skip expired
                        except Exception:
                            pass
                    existing_names.append(s.name)
                existing = ", ".join(existing_names) if existing_names else "none"
            except Exception:
                existing = "none"

            msg = (
                f"Existing memex skills: {existing}\n\n"
                f"Recent conversation:\n{conversation}"
            )

            response = await agent.call_utility_model(
                system=system,
                message=msg,
                background=True,
            )
            if not response:
                return

            result = DirtyJson.parse_string(response)
            if not isinstance(result, dict):
                return

            action = result.get("action", "skip")
            if action == "skip":
                return

            name = result.get("name", "").strip()
            title = result.get("title", "").strip()
            content = result.get("content", "").strip()
            triggers = result.get("triggers", [])
            tags = result.get("tags", [])

            if not name or not content:
                return

            if not isinstance(triggers, list):
                triggers = []
            if not isinstance(tags, list):
                tags = []

            index.save_skill(name, title or name, content, triggers, tags, agent=agent)
            if len(_skills_created) > 1000:
                _skills_created.clear()
            _skills_created[ctx_id] = _skills_created.get(ctx_id, 0) + 1

            PrintStyle(
                font_color="#1B4F72",
                padding=True,
            ).print(f"[Memex Skill] Created/updated skill: {name}")

        except Exception as e:
            PrintStyle(
                font_color="red",
            ).print(f"[Memex Skill] Error in skill nudge: {e}")

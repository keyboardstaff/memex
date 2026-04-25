import datetime
from helpers.tool import Tool, Response


class SkillManage(Tool):
    """Tool for managing memex procedural skills."""

    async def execute(self, action="", name="", title="", content="",
                      triggers="", tags="", query="", expires="", **kwargs):
        from helpers import files

        if action in ("create", "update"):
            from usr.plugins.memex.helpers.memex_skill_index import SkillIndex
            if not name or not content:
                return Response(
                    message="Error: name and content required.",
                    break_loop=False,
                )
            trigger_list = (
                [t.strip() for t in triggers.split(",") if t.strip()]
                if triggers
                else []
            )
            tag_list = (
                [t.strip() for t in tags.split(",") if t.strip()]
                if tags
                else []
            )
            path = SkillIndex().save_skill(
                name, title or name, content, trigger_list, tag_list,
                expires=expires or None,
                agent=self.agent,
            )
            verb = "updated" if action == "update" else "created"
            return Response(
                message=f"Skill '{name}' {verb} at {path}",
                break_loop=False,
            )

        elif action == "list":
            try:
                from helpers.skills import list_skills
                all_skills = list_skills(self.agent, include_content=True)
            except Exception:
                all_skills = []
            _now = datetime.datetime.now(tz=datetime.timezone.utc)
            memex_skills = [s for s in all_skills if "memex-auto" in s.tags]
            if not memex_skills:
                return Response(message="No memex-auto skills found.", break_loop=False)
            def _skill_line(s):
                exp = s.raw_frontmatter.get("expires")
                tag = ""
                if exp:
                    try:
                        exp_dt = datetime.datetime.fromisoformat(str(exp))
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
                        tag = " [EXPIRED]" if exp_dt < _now else f" [expires {str(exp)[:10]}]"
                    except Exception:
                        pass
                return f"- {s.name}: {s.description}{tag}"
            lines = [_skill_line(s) for s in sorted(memex_skills, key=lambda x: x.name)]
            return Response(
                message=f"Memex-auto skills ({len(lines)}):\n" + "\n".join(lines),
                break_loop=False,
            )

        elif action == "view":
            if not name:
                return Response(
                    message="Error: skill name required.",
                    break_loop=False,
                )
            try:
                from helpers.skills import find_skill
                skill = find_skill(name, agent=self.agent, include_content=True)
            except Exception:
                skill = None
            if not skill:
                return Response(
                    message=f"Skill '{name}' not found.",
                    break_loop=False,
                )
            body = skill.content or files.read_file(str(skill.skill_md_path))
            _now = datetime.datetime.now(tz=datetime.timezone.utc)
            exp = skill.raw_frontmatter.get("expires")
            if exp:
                try:
                    exp_dt = datetime.datetime.fromisoformat(str(exp))
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
                    status = "EXPIRED" if exp_dt < _now else f"expires {str(exp)[:10]}"
                    body = f"⚠ [{status}]\n\n{body}"
                except Exception:
                    pass
            return Response(message=body, break_loop=False)

        elif action == "search":
            from usr.plugins.memex.helpers.memex_skill_index import SkillIndex
            if not query:
                return Response(
                    message="Error: search query required.",
                    break_loop=False,
                )
            matches = SkillIndex().search_unified(query, agent=self.agent, limit=10)
            if not matches:
                return Response(
                    message=f"No skills matching '{query}'.",
                    break_loop=False,
                )
            lines = [
                f"- [{m['source']}] {m['name']}: {m['description']} (tags: {', '.join(m['tags'])})"
                for m in matches
            ]
            return Response(
                message="Matching skills:\n" + "\n".join(lines),
                break_loop=False,
            )

        elif action == "delete":
            if not name:
                return Response(
                    message="Error: skill name required.",
                    break_loop=False,
                )
            try:
                from helpers.skills import find_skill, delete_skill
                skill = find_skill(name, agent=self.agent)
                if not skill:
                    return Response(
                        message=f"Skill '{name}' not found.",
                        break_loop=False,
                    )
                delete_skill(str(skill.path))
                return Response(
                    message=f"Skill '{name}' deleted.",
                    break_loop=False,
                )
            except FileNotFoundError:
                return Response(message=f"Skill '{name}' not found.", break_loop=False)
            except Exception as e:
                return Response(message=f"Error deleting skill: {e}", break_loop=False)

        return Response(
            message=f"Unknown action: {action}. Use create/update/list/view/search/delete.",
            break_loop=False,
        )

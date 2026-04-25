import os
from helpers import files

try:
    import yaml
except Exception:
    yaml = None


class SkillIndex:
    """Write and search memex-auto skills via A0 native skills paths."""

    def save_skill(
        self,
        name: str,
        title: str,
        content: str,
        triggers: list[str],
        tags: list[str],
        requires_tools: list[str] | None = None,
        expires: str | None = None,
        agent=None,
    ) -> str:
        if not yaml:
            raise RuntimeError("PyYAML is required to save skills")

        safe_name = name.lower().replace(" ", "-").replace("/", "-")

        skill_root = self._resolve_skill_root(agent)
        skill_dir = os.path.join(skill_root, safe_name)
        os.makedirs(skill_dir, exist_ok=True)
        path = os.path.join(skill_dir, "SKILL.md")

        version = "1"
        if os.path.isfile(path):
            try:
                existing_content = files.read_file(path)
                end = existing_content.index("---", 3)
                fm = yaml.safe_load(existing_content[3:end]) or {}
                version = str(int(fm.get("version", "1")) + 1)
            except Exception:
                pass

        if "memex-auto" not in tags:
            tags = ["memex-auto"] + list(tags)

        frontmatter: dict = {
            "name": safe_name,
            "description": title,
            "version": version,
            "author": "memex-auto",
            "tags": tags,
            "triggers": triggers,
        }
        if requires_tools:
            frontmatter["allowed_tools"] = requires_tools
        if expires:
            frontmatter["expires"] = expires

        fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        files.write_file(path, f"---\n{fm_str}---\n\n# {title}\n\n{content}")
        return path

    @staticmethod
    def _resolve_skill_root(agent=None) -> str:
        if agent is not None:
            try:
                from helpers import projects
                project_name = projects.get_context_project_name(agent.context)
                if project_name:
                    return projects.get_project_meta(project_name, "skills")
            except Exception:
                pass
        return files.get_abs_path("usr/skills")

    def search_unified(self, query: str, agent=None, limit: int = 10) -> list[dict]:
        """Search A0 native skills, re-ranked by usage frequency."""
        try:
            from helpers.skills import search_skills
            from usr.plugins.memex.helpers.memex_skill_usage import get_counts
            hits = search_skills(query, limit=limit * 2, agent=agent)
            usage = get_counts()
            results = [
                {
                    "name": s.name,
                    "description": s.description,
                    "tags": s.tags,
                    "source": "memex-auto" if "memex-auto" in s.tags else "a0",
                    "_usage": usage.get(s.name, 0),
                }
                for s in hits
            ]
            # Re-rank by usage
            import math
            results.sort(key=lambda r: -math.log1p(r["_usage"]))
            for r in results:
                del r["_usage"]
            return results[:limit]
        except Exception:
            return []

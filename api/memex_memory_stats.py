import os
from helpers.api import ApiHandler, Request, Response


class MemoryStatsApi(ApiHandler):

    async def process(self, input: dict, request: Request) -> dict | Response:
        from usr.plugins.memex.helpers.memex_decay import get_stats as decay_stats
        from usr.plugins.memex.helpers.memex_nudge_engine import _load_state
        from usr.plugins.memex.helpers.memex_portrait import load_portrait

        subdir = input.get("memory_subdir") or None
        project_name = subdir[9:] if subdir and subdir.startswith("projects/") else ""

        # Available subdirs
        try:
            from plugins._memory.helpers.memory import get_existing_memory_subdirs
            available_subdirs = get_existing_memory_subdirs()
            # Also include projects without memory yet
            try:
                from helpers.projects import get_projects_parent_folder
                from helpers import files as hfiles
                all_projects = hfiles.get_subdirectories(get_projects_parent_folder())
                for p in all_projects:
                    key = f"projects/{p}"
                    if key not in available_subdirs:
                        available_subdirs.append(key)
            except Exception:
                pass
        except Exception:
            available_subdirs = ["default"]

        # Decay stats
        decay = decay_stats(subdir)

        # Session stats
        try:
            from usr.plugins.memex.helpers.memex_session_index import SessionIndex
            si = SessionIndex()
            session = si.get_stats(project_name=project_name)
        except Exception:
            session = {"sessions": 0, "messages": 0}

        # Nudge state
        _nudge_state = _load_state()
        if subdir:
            _cursor = _nudge_state.get("cursor", {}).get(subdir, {})
            nudge = {
                "insights_generated": _cursor.get("insights_generated", 0),
                "memories_archived": _cursor.get("memories_archived", 0),
                "last_nudge_time": _nudge_state.get("last_nudge_time"),
            }
        else:
            nudge = _nudge_state

        # Portrait stats
        try:
            portrait = load_portrait()
            portrait_data = {
                "traits": len(portrait.traits),
                "established": len(portrait.get_established_traits()),
                "last_updated": portrait.last_updated,
            }
        except Exception:
            portrait_data = {"traits": 0, "established": 0, "last_updated": ""}

        # Skills stats
        try:
            from helpers import files as hfiles

            def _count_memex_skills(skill_root: str):
                from helpers.skills import discover_skill_md_files, skill_from_markdown
                from pathlib import Path
                if not os.path.isdir(skill_root):
                    return 0, None
                count = 0
                latest = None
                for skill_md in discover_skill_md_files(Path(skill_root)):
                    s = skill_from_markdown(skill_md)
                    if not s or "memex-auto" not in s.tags:
                        continue
                    count += 1
                    mtime = os.path.getmtime(str(skill_md))
                    if latest is None or mtime > latest:
                        latest = mtime
                return count, latest

            if subdir and subdir.startswith("projects/"):
                _proj = subdir[9:]
                from helpers import projects as hprojects
                skill_root = hprojects.get_project_meta(_proj, "skills")
                memex_count, latest_mtime = _count_memex_skills(skill_root)
            elif not subdir:
                # All roots
                import glob
                roots = [hfiles.get_abs_path("usr/skills")]
                roots += glob.glob(hfiles.get_abs_path("usr/projects/*/.a0proj/skills"))
                memex_count = 0
                latest_mtime = None
                for root in roots:
                    c, m = _count_memex_skills(root)
                    memex_count += c
                    if m and (latest_mtime is None or m > latest_mtime):
                        latest_mtime = m
            else:
                # Global root
                skill_root = hfiles.get_abs_path("usr/skills")
                memex_count, latest_mtime = _count_memex_skills(skill_root)

            import datetime
            last_updated_iso = (
                datetime.datetime.fromtimestamp(latest_mtime, tz=datetime.timezone.utc).isoformat()
                if latest_mtime else None
            )
            skills_data = {
                "total": memex_count,
                "last_updated": last_updated_iso,
            }
        except Exception:
            skills_data = {"total": 0, "last_updated": None}

        # Recall stats
        try:
            from usr.plugins.memex.helpers.memex_skill_usage import get_recall_stats
            recall_stats = get_recall_stats()
            skills_data["recall_rate"] = recall_stats["rate"]
            skills_data["recall_attempts"] = recall_stats["attempts"]
        except Exception:
            skills_data["recall_rate"] = 0.0
            skills_data["recall_attempts"] = 0

        # Chapters stats
        try:
            from usr.plugins.memex.helpers.memex_chapters import get_stats as chapters_get_stats
            chapters_data = chapters_get_stats(project_name=project_name)
        except Exception:
            chapters_data = {"total": 0, "total_tokens_preserved": 0, "last_compressed": None}

        return {
            "ok": True,
            "available_subdirs": available_subdirs,
            "decay": decay,
            "session": session,
            "nudge": nudge,
            "portrait": portrait_data,
            "skills": skills_data,
            "chapters": chapters_data,
        }

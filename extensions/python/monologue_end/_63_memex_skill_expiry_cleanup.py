import os
import datetime
from helpers.extension import Extension
from helpers import plugins, files
from agent import LoopData

_STATE_FILE = "usr/plugins/memex/data/expiry_cleanup_state.json"


def _load_state() -> dict:
    import json
    path = files.get_abs_path(_STATE_FILE)
    if not os.path.isfile(path):
        return {}
    try:
        return json.loads(files.read_file(path)) or {}
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    import json
    files.write_file(files.get_abs_path(_STATE_FILE), json.dumps(state))


class SkillExpiryCleanup(Extension):
    """Delete expired memex-auto skills on a configurable schedule."""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("skills_enabled", True):
            return
        if not config.get("skills_expiry_enabled", False):
            return

        interval_hours = config.get("skills_expiry_cleanup_interval_hours", 24)
        state = _load_state()
        last_run_str = state.get("last_run")
        if last_run_str:
            try:
                last_run = datetime.datetime.fromisoformat(last_run_str)
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=datetime.timezone.utc)
                elapsed = (datetime.datetime.now(datetime.timezone.utc) - last_run).total_seconds()
                if elapsed < interval_hours * 3600:
                    return
            except Exception:
                pass

        deleted = self._cleanup_expired()

        state["last_run"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state["last_deleted"] = deleted
        _save_state(state)

        if deleted:
            from helpers.print_style import PrintStyle
            PrintStyle(font_color="#1B4F72", padding=True).print(
                f"[Memex Skill Expiry] Removed {deleted} expired skill(s)."
            )

    def _cleanup_expired(self) -> int:
        """Delete all expired memex- skills. Returns count of deleted skills."""
        try:
            from helpers.skills import list_skills, delete_skill
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            deleted = 0
            for s in list_skills(self.agent, include_content=True):
                if "memex-auto" not in s.tags:
                    continue
                exp = s.raw_frontmatter.get("expires")
                if not exp:
                    continue
                try:
                    exp_dt = datetime.datetime.fromisoformat(str(exp))
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
                    if exp_dt < now:
                        delete_skill(str(s.path))
                        deleted += 1
                except Exception:
                    pass
            return deleted
        except Exception:
            return 0

import time
from helpers.extension import Extension
from helpers import plugins
from helpers.defer import DeferredTask, THREAD_BACKGROUND

_last_decay_run = 0


class DecayUpdate(Extension):

    async def execute(self, **kwargs):
        global _last_decay_run
        now = time.time()

        config = plugins.get_plugin_config("memex")
        if not config or not config.get("decay_enabled", True):
            return

        interval = config.get("decay_update_interval_minutes", 30) * 60
        if now - _last_decay_run < interval:
            return
        _last_decay_run = now

        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(self._run_decay)

    @staticmethod
    async def _run_decay():
        from usr.plugins.memex.helpers.memex_decay import expire_boosts
        expire_boosts()

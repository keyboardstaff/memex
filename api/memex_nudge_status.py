from helpers.api import ApiHandler, Request, Response


class NudgeStatusApi(ApiHandler):

    async def process(self, input: dict, request: Request) -> dict | Response:
        from usr.plugins.memex.helpers.memex_nudge_engine import _load_state

        state = _load_state()
        return {"success": True, "state": state}

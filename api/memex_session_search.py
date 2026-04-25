from helpers.api import ApiHandler, Request, Response


class SessionSearchApi(ApiHandler):

    async def process(self, input: dict, request: Request) -> dict | Response:
        from usr.plugins.memex.helpers.memex_session_index import SessionIndex

        action = input.get("action", "search")

        if action == "search":
            query = input.get("query", "")
            if not query:
                return {"success": False, "error": "Query is required"}

            index = SessionIndex()
            results = index.search(
                query=query,
                project_name=input.get("project", ""),
                limit=input.get("limit", 20),
                offset=input.get("offset", 0),
            )
            return {"success": True, "results": results, "count": len(results)}

        elif action == "context":
            context_id = input.get("context_id", "")
            message_index = input.get("message_index", 0)
            if not context_id:
                return {"success": False, "error": "context_id is required"}

            index = SessionIndex()
            context = index.get_session_context(context_id, int(message_index))
            return {"success": True, "messages": context}

        elif action == "stats":
            index = SessionIndex()
            return {"success": True, "stats": index.get_stats()}

        return {"success": False, "error": f"Unknown action: {action}"}

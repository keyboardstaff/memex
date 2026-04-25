from helpers.tool import Tool, Response


class SessionSearch(Tool):

    async def execute(self, query="", project="", limit=10, **kwargs):
        if not query:
            return Response(
                message="Error: search query is required.",
                break_loop=False,
            )

        from usr.plugins.memex.helpers.memex_session_index import SessionIndex

        index = SessionIndex()
        results = index.search(query=query, project_name=project, limit=int(limit))

        if not results:
            return Response(
                message=f"No sessions found matching '{query}'.",
                break_loop=False,
            )

        formatted = []
        for r in results:
            formatted.append(
                f"**Session {r['context_id'][:8]}** "
                f"({r['session_started'][:10]}, {r['project_name'] or 'no project'})\n"
                f"  [{r['role']}]: {r['snippet']}"
            )

        text = f"Found {len(results)} results for '{query}':\n\n" + "\n\n".join(formatted)
        return Response(message=text, break_loop=False)

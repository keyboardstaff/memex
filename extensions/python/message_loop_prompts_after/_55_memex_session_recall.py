from helpers.extension import Extension
from helpers import plugins, projects
from agent import LoopData


class SessionRecall(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config("memex", self.agent)
        if not config or not config.get("session_search_enabled", True):
            return
        if not config.get("session_proactive_recall", True):
            return

        # Only trigger on first iteration
        if loop_data.iteration > 0:
            return

        user_msg = ""
        msgs = self.agent.history.current.messages
        for m in msgs:
            if not m.ai:
                user_msg = m.output_text()
                break

        if not user_msg or len(user_msg) < 10:
            return

        from usr.plugins.memex.helpers.memex_session_index import SessionIndex

        index = SessionIndex()

        project = projects.get_context_project_name(self.agent.context) or ""
        limit = config.get("session_proactive_limit", 5)
        results = index.search(
            query=user_msg[:500],
            project_name=project,
            limit=limit,
        )

        # Filter out current session
        results = [r for r in results if r["context_id"] != self.agent.context.id]

        if results:
            context_text = "\n".join(
                f"- [{r['session_started'][:10]}] {r['role']}: {r['snippet']}"
                for r in results[:3]
            )
            extras = loop_data.extras_temporary
            extras["session_history"] = self.agent.parse_prompt(
                "session.recall.msg.md",
                past_conversations=context_text,
            )

        # Knowledge recall from vector DB (Proposal D)
        if config.get("knowledge_proactive_recall", True):
            kn_limit = config.get("knowledge_proactive_limit", 3)
            await _inject_knowledge_recall(self.agent, loop_data, user_msg, kn_limit)


async def _inject_knowledge_recall(agent, loop_data: LoopData, query: str, limit: int) -> None:
    try:
        from plugins._memory.helpers.memory import Memory

        memory = await Memory.get(agent)
        docs = await memory.search_similarity_threshold(
            query=query[:500],
            limit=limit,
            threshold=0.65,
            filter={"area": "knowledge_source"},
        )
        if not docs:
            return

        snippets = "\n\n".join(
            f"[{d.metadata.get('source_file', 'knowledge')}]: {d.page_content[:400]}"
            for d in docs
        )

        extras = loop_data.extras_temporary
        extras["knowledge_recall"] = agent.parse_prompt(
            "knowledge.recall.msg.md",
            knowledge_snippets=snippets,
        )
    except Exception:
        pass

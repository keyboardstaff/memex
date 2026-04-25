# Memex

Persistent memory layer for Agent Zero — cross-session search, decay scoring, user profiling, auto skill learning, intelligent nudges, and session chapters.

## What It Does

This plugin provides persistent memory capabilities across conversations, automatically indexing sessions for search, building user portraits from interactions, applying decay-based priority scoring to memories, generating insights via LLM nudges, auto-generating skills based on usage patterns, and capturing session chapters before auto-compaction.

## Main Behavior

- **Session indexing and search**
  - Indexes completed conversations into FTS5 SQLite for full-text search with relevance ranking.
  - Proactively recalls relevant history into prompts.
- **Session chapters**
  - Snapshots full conversation history into plain-text chapters before A0 auto-compaction.
  - Tree-structured metadata (parent_id, chapter_index) in `session_index.db`; text saved to `data/chapters/<id>.txt` at runtime.
- **User portraiture**
  - Builds dialectic traits (thesis → synthesis) from observations via `DialecticModeler`, injects high-confidence traits (≥0.5) into `extras.user_preferences`.
  - Trait categories (`TraitCategory`) and confidence levels defined in `memex_trait_taxonomy.py`.
- **Memory decay and reranking**
  - Computes priority scores blending similarity, recency (half-life 14 days), access frequency, and importance.
  - Records `memory_load` accesses after tool execution; reranks recalled memories before prompt injection.
- **Nudge engine**
  - Periodically reviews old memories (>48h), extracts cross-memory insights via LLM, adjusts importance, archives low-value items.
- **Auto skills**
  - Tracks skill usage counts, re-ranks and loads relevant skills, generates `memex-auto` skills in `/a0/usr/skills/`.
  - Enforces a `skills_max_loaded` rolling window; reviews heavily-used skills and proposes improvements.
  - Optionally expires and cleans up stale auto-generated skills.
- **Dashboard support**
  - Sidebar UI for stats, search, nudge status, and portrait viewer.

## Key Files

- **Core logic**
  - `helpers/memex_db.py`: Session/memory DB connections and schema.
  - `helpers/memex_chapters.py`: Session chapter snapshots for auto-compact (tree-structured history preservation).
  - `helpers/memex_portrait.py`: Trait modeling and injection.
  - `helpers/memex_trait_taxonomy.py`: `TraitCategory` enums and `UserTrait` dataclasses for portrait modeling.
  - `helpers/memex_dialectic_modeler.py`: `DialecticModeler` — extracts trait observations from conversations and updates portrait.
  - `helpers/memex_session_index.py`: FTS5 indexing and search for completed sessions.
  - `helpers/memex_decay.py`: Priority score computation, access recording, and boost expiry.
  - `helpers/memex_nudge_engine.py`: LLM review cycles, insight extraction, and importance adjustment.
  - `helpers/memex_skill_index.py`: Skill FTS indexing, auto-generation, and native skill re-ranking.
  - `helpers/memex_skill_usage.py`: Lightweight skill recall usage counter, persisted to `data/skill_usage.json`.
- **Extensions**
  - `extensions/python/system_prompt/_25_memex_portrait_prompt.py`: Injects portrait summary into the system prompt.
  - `extensions/python/message_loop_prompts_before/_88_memex_auto_compact_check.py`: Snapshots conversation into a chapter before A0 auto-compaction.
  - `extensions/python/message_loop_prompts_after/_52_memex_portrait_inject.py`: Injects high-confidence portrait traits into `extras.user_preferences`.
  - `extensions/python/message_loop_prompts_after/_53_memex_decay_rerank.py`: Reranks recalled memories by decay priority score.
  - `extensions/python/message_loop_prompts_after/_55_memex_session_recall.py`: Proactively recalls relevant session history into the prompt.
  - `extensions/python/message_loop_prompts_after/_64_memex_skill_recall.py`: Proactively recalls and loads relevant skills.
  - `extensions/python/monologue_end/_60_memex_session_index.py`: Indexes the completed conversation into the FTS5 session DB.
  - `extensions/python/monologue_end/_61_memex_portrait_update.py`: Updates user portrait traits from the completed conversation.
  - `extensions/python/monologue_end/_62_memex_skill_nudge.py`: Triggers skill indexing and nudge after each monologue.
  - `extensions/python/monologue_end/_63_memex_skill_expiry_cleanup.py`: Periodically removes expired auto-generated skills.
  - `extensions/python/monologue_end/_64_memex_skill_improve.py`: Reviews heavily-used `memex-auto` skills and proposes improvements via LLM.
  - `extensions/python/tool_execute_after/_60_memex_decay_access.py`: Records `memory_load` tool accesses for decay scoring.
  - `extensions/python/tool_execute_after/_64_memex_cap_loaded_skills.py`: Enforces the `skills_max_loaded` rolling window after skill loads.
  - `extensions/python/job_loop/_60_memex_memory_nudge.py`: Periodic memory nudge review cycle (background job).
  - `extensions/python/job_loop/_61_memex_decay_update.py`: Periodic decay score recalculation and boost expiry (background job).
- **Tools**
  - `tools/memex_session_search.py`: Agent tool for full-text session search.
  - `tools/memex_skill_manage.py`: Agent tool for skill management (list, activate, deactivate).
- **API**
  - `api/memex_session_search.py`: REST endpoint for session search.
  - `api/memex_memory_stats.py`: REST endpoint for memory stats (dashboard).
  - `api/memex_nudge_status.py`: REST endpoint for nudge engine status.
- **WebUI**
  - `webui/main.html`: Sidebar dashboard panel (stats, search, nudge status, portrait viewer).
  - `webui/config.html`: Plugin settings panel.
  - `webui/memex-dashboard-store.js`: Frontend state store for the dashboard.
- **Data storage**
  - `data/sessions.db`: FTS5 full-text search index of conversations.
  - `data/session_index.db`: Chapter metadata (parent_id, chapter_index tree).
  - `data/memory.db`: Memory access logs for decay scoring.
  - `data/portrait.json`: Persistent user trait model.
  - `data/nudge.json`: Nudge engine state (last run, processed items).
  - `data/expiry_cleanup_state.json`: Skill expiry cleanup scheduler state.
  - `data/skill_usage.json`: Skill recall usage counters (created at runtime).
  - `data/chapters/<id>.txt`: Plain-text chapter snapshots (created at runtime).

## Configuration Scope

- **Settings section**: `agent`
- **Per-project config**: `true`
- **Per-agent config**: `true`

## Plugin Metadata

- **Name**: `memex`
- **Title**: `Memex`
- **Description**: Persistent memory layer — cross-session search, decay scoring, user profiling, and auto skill learning.
- **Version**: `0.1.0`
# 13: Notion sync — curated push of promoted entries

**What to build:** A `push_to_notion` MCP tool that pushes entries tagged as actionable content (`youtube-idea`, `instagram-idea`, or manually flagged) from Supabase into a Notion database via the Notion MCP. Notion becomes the lightweight mobile-accessible action surface — a curated view of ideas ready to act on, not a dump of the full KB.

**Blocked by:** 08 — MCP server core tools

**Status:** blocked

**Tool:**

- `push_to_notion(entry_id?, tag?, limit?)`:
  - If `entry_id` provided: pushes that specific entry
  - If `tag` provided: pushes all entries with that tag not yet synced to Notion
  - If neither: pushes all `youtube-idea` and `instagram-idea` entries created in the last 7 days not yet synced
  - Each pushed entry creates a Notion page with: title (first sentence of content), topic_label, mood, tags, recorded_at, link back to source file

- [ ] Notion database created with correct properties (Title, Topic, Mood, Tags, Date, Source)
- [ ] `push_to_notion` tool calls Notion MCP to create pages — no direct Notion API calls needed
- [ ] Entries are not pushed twice — a `notion_page_id` column added to `entries` table tracks what has been synced
- [ ] Running `push_to_notion(tag="youtube-idea")` in Claude Desktop produces visible Notion pages
- [ ] Notion database is accessible on Notion mobile app

## Comments

2026-09-26 implementation evidence:

- Created the private Notion database **Personal KB — Actionable Ideas** with the required Title, Topic, Mood, Tags, Date, and Source properties. Its data source is `04b2ca0d-9e4b-4a8a-84ca-047b9d8376c9`.
- Added and applied Supabase migration `20260926020000_add_notion_page_id.sql`. A live Supabase query confirmed the `notion_page_id` column is available and found 3 unsynced actionable entries in the sampled data.
- Implemented the `push_to_notion(entry_id?, tag?, limit?)` MCP tool. It selects only unsynced candidates, builds the required database properties, invokes a configured Streamable-HTTP Notion MCP server (never the Notion REST API), and writes the returned page ID only after successful page creation. `entry_id` is the manual one-off promotion path; default mode selects recent `youtube-idea` / `instagram-idea` entries.
- Verification: `python -m pytest tests/test_mcp_server.py tests/test_notion.py -q` passed (20 tests); full `python -m pytest -q` passed (60 tests, 3 pre-existing integration skips). The migration was applied with `npx supabase db push`.
- Mandatory two-axis review completed. Standards found and fixed one misleading local variable name. Spec review found that live page/mobile verification and a configured transport remain external requirements.

Blocked external requirements:

- `.env` has no `NOTION_MCP_URL`, so the MCP server cannot reach the connected Notion workspace to create and observe a real page. `NOTION_DATA_SOURCE_ID` also needs to be configured for the created database. A direct Notion API fallback was intentionally not added.
- The requested Claude Desktop run and Notion mobile visibility must be performed after that MCP transport is supplied. The corresponding checkboxes remain unchecked until those observations are made.

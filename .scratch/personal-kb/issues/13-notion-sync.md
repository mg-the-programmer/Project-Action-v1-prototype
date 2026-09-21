# 13: Notion sync — curated push of promoted entries

**What to build:** A `push_to_notion` MCP tool that pushes entries tagged as actionable content (`youtube-idea`, `instagram-idea`, or manually flagged) from Supabase into a Notion database via the Notion MCP. Notion becomes the lightweight mobile-accessible action surface — a curated view of ideas ready to act on, not a dump of the full KB.

**Blocked by:** 08 — MCP server core tools

**Status:** ready-for-agent

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

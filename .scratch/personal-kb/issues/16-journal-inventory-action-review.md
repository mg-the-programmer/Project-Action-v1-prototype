# Journal inventory and reviewable action suggestions

Status: resolved
Type: task
Blocked by: none

## Goal

Make ingested `voice_memo` sources visible as journals in the local dashboard and
provide a durable, review-only queue of AI-suggested action items. Suggestions
must retain source evidence and must never create tasks in Notion or another
external system.

## Acceptance criteria

- The API inventories voice-memo journals by `source_file`, with a display name,
  recorded range, canonical chunk count, labels, and retrievable source context.
- A migration persists action suggestions, source linkage/evidence, status, and
  an extraction marker that makes backfills explicit and idempotent.
- An explicit OpenAI-compatible extraction command processes current journals;
  invalid or unsupported suggestions are not stored.
- The dashboard lets a person inspect journal context and approve or dismiss a
  suggestion, with useful empty states.
- Tests cover the service/API and extraction behaviour, and the dashboard builds.

## Evidence

- Added migration `20260926030000_add_journal_action_items.sql` and applied it
  to the configured Supabase project.
- `python -m pytest -q -m 'not integration'` passed: 72 tests.
- `python -m pytest tests/test_journal_actions_live.py -q` passed against
  Supabase; its isolated entry, actions, and extraction marker were deleted.
- `cd dashboard; npm run build` passed.
- Read-only Supabase inventory check found 3 existing voice journals.
- Two-axis review against `351614a...38767d6`: standards had no findings;
  spec found unsupported wording and missing live persistence coverage. Both
  were addressed before this ticket was resolved.

## Comments

- Action wording is accepted only when its terms occur in the model's cited,
  verbatim evidence, so an unrelated todo cannot be stored merely by quoting a
  nearby chunk.

# Journal inventory and reviewable action suggestions

Status: claimed
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

Pending implementation.

## Comments


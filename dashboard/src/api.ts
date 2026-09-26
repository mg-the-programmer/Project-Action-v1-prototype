export type Entry = {
  id: string;
  content: string;
  source_type: string;
  source_file?: string | null;
  audio_offset?: number | null;
  chunk_index?: number | null;
  tags?: string[] | null;
  mood?: string | null;
  topic_label?: string | null;
  moment_type?: string | null;
  visual_context?: string | null;
  recorded_at?: string | null;
  created_at?: string | null;
  blended_score?: number;
};

export type RetrievalLog = { id: string; query: string; results: unknown[]; rating?: number | null; comment?: string | null; created_at: string };
export type TriggerWord = { id?: string; word: string; added_at?: string };
export type Journal = { source_file: string; journal_name: string; recorded_start?: string | null; recorded_end?: string | null; chunk_count: number; tags: string[]; labels: string[] };
export type JournalChunk = Pick<Entry, "id" | "content" | "chunk_index" | "audio_offset" | "recorded_at">;
export type JournalAction = { id: string; source_file: string; source_entry_id: string; wording: string; evidence: string; status: "suggested" | "approved" | "dismissed"; extracted_at: string; reviewed_at?: string | null };

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) {
    const message = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(message?.detail ?? `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const dashboardApi = {
  entries: () => request<Entry[]>("/entries"),
  search: (query: string) => request<{ log_id: string; results: Entry[] }>("/search", { method: "POST", body: JSON.stringify({ query }) }),
  logs: () => request<RetrievalLog[]>("/retrieval-logs"),
  triggerWords: () => request<TriggerWord[]>("/trigger-words"),
  addTriggerWord: (word: string) => request<TriggerWord>("/trigger-words", { method: "POST", body: JSON.stringify({ word }) }),
  removeTriggerWord: (word: string) => request<{ word: string }>(`/trigger-words/${encodeURIComponent(word)}`, { method: "DELETE" }),
  journals: () => request<Journal[]>("/journals"),
  journalContext: (sourceFile: string) => request<JournalChunk[]>(`/journals/context?source_file=${encodeURIComponent(sourceFile)}`),
  journalActions: () => request<JournalAction[]>("/journal-actions"),
  reviewJournalAction: (actionId: string, status: "approved" | "dismissed") => request<JournalAction>(`/journal-actions/${encodeURIComponent(actionId)}/review`, { method: "POST", body: JSON.stringify({ status }) }),
  extractJournalActions: () => request<{ journals_processed: number; suggestions_found: number; journals_skipped: number }>("/journal-actions/extract", { method: "POST", body: JSON.stringify({}) }),
  audioUrl: (entryId: string, offset: number) => `${API_URL}/entries/${encodeURIComponent(entryId)}/audio#t=${Math.floor(offset)}`,
};

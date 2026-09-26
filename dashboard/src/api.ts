export type Entry = {
  id: string;
  content: string;
  source_type: string;
  source_file?: string | null;
  audio_offset?: number | null;
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
  audioUrl: (entryId: string, offset: number) => `${API_URL}/entries/${encodeURIComponent(entryId)}/audio#t=${Math.floor(offset)}`,
};

import { FormEvent, useEffect, useMemo, useState } from "react";
import { dashboardApi, Entry, Journal, JournalAction, JournalChunk, RetrievalLog, TriggerWord } from "./api";

type Range = "30" | "90" | "all";
type LoadState = "loading" | "ready" | "error";

const moods = ["excited", "happy", "reflective", "frustrated", "curious", "neutral"];
const moodColors: Record<string, string> = {
  excited: "#f59e0b", happy: "#ec4899", reflective: "#818cf8",
  frustrated: "#fb7185", curious: "#22d3ee", neutral: "#94a3b8",
};

function formatDate(value?: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value)) : "Undated";
}

function formatOffset(seconds?: number | null) {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return null;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function withinRange(entry: Entry, range: Range) {
  if (range === "all" || !entry.recorded_at) return true;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - Number(range));
  return new Date(entry.recorded_at) >= cutoff;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-lg shadow-slate-950/20"><h2 className="mb-4 text-lg font-semibold text-white">{title}</h2>{children}</section>;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border border-dashed border-slate-700 p-4 text-sm text-slate-400">{children}</p>;
}

function MoodTrend({ entries }: { entries: Entry[] }) {
  const rows = useMemo(() => {
    const byDay = new Map<string, Record<string, number>>();
    entries.forEach((entry) => {
      if (!entry.recorded_at || !entry.mood) return;
      const day = entry.recorded_at.slice(0, 10);
      const counts = byDay.get(day) ?? {};
      counts[entry.mood] = (counts[entry.mood] ?? 0) + 1;
      byDay.set(day, counts);
    });
    return [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [entries]);
  const max = Math.max(1, ...rows.flatMap(([, counts]) => Object.values(counts)));

  if (!rows.length) return <Empty>No dated, mood-tagged entries are available for this range.</Empty>;
  const width = 600; const height = 180; const padding = 18;
  const x = (index: number) => rows.length === 1 ? width / 2 : padding + (index * (width - 2 * padding)) / (rows.length - 1);
  const y = (count: number) => height - padding - (count * (height - 2 * padding)) / max;
  return <div><svg role="img" aria-label="Mood distribution over time" viewBox={`0 0 ${width} ${height}`} className="w-full rounded bg-slate-950"><line x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} stroke="#334155" />{moods.map((mood) => <polyline key={mood} fill="none" stroke={moodColors[mood]} strokeWidth="2.5" points={rows.map(([, counts], index) => `${x(index)},${y(counts[mood] ?? 0)}`).join(" ")}><title>{mood}</title></polyline>)}</svg><div className="mt-2 flex flex-wrap gap-3 text-xs">{moods.map((mood) => <span key={mood} className="capitalize" style={{ color: moodColors[mood] }}>● {mood}</span>)}</div></div>;
}

function TopicDistribution({ entries }: { entries: Entry[] }) {
  const topics = useMemo(() => {
    const counts = new Map<string, number>();
    entries.forEach((entry) => { if (entry.topic_label) counts.set(entry.topic_label, (counts.get(entry.topic_label) ?? 0) + 1); });
    return [...counts.entries()].sort(([, left], [, right]) => right - left);
  }, [entries]);
  const max = Math.max(1, ...topics.map(([, count]) => count));
  if (!topics.length) return <Empty>No topic labels are available yet.</Empty>;
  return <div className="space-y-3">{topics.map(([topic, count]) => <div key={topic}><div className="mb-1 flex justify-between text-sm"><span className="capitalize text-slate-300">{topic.replaceAll("-", " ")}</span><span className="text-slate-400">{count}</span></div><div className="h-2 rounded bg-slate-800"><div className="h-2 rounded bg-cyan-400" style={{ width: `${(count / max) * 100}%` }} /></div></div>)}</div>;
}

function EvalMetrics({ logs }: { logs: RetrievalLog[] }) {
  const rated = logs.filter((log) => log.rating != null);
  const average = rated.length ? rated.reduce((sum, log) => sum + (log.rating ?? 0), 0) / rated.length : null;
  const distribution = [1, 2, 3, 4, 5].map((rating) => [rating, rated.filter((log) => log.rating === rating).length] as const);
  const low = rated.filter((log) => (log.rating ?? 5) <= 2).slice(0, 5);
  return <div className="space-y-4"><div className="flex items-end justify-between"><div><p className="text-3xl font-bold text-cyan-300">{average?.toFixed(1) ?? "—"}<span className="text-base text-slate-400"> / 5</span></p><p className="text-sm text-slate-400">average rating ({rated.length} rated searches)</p></div><p className="text-sm text-slate-400">{logs.length} total searches</p></div><div className="flex gap-2">{distribution.map(([rating, count]) => <div key={rating} className="flex-1 rounded bg-slate-800 p-2 text-center"><b className="block text-cyan-200">{count}</b><span className="text-xs text-slate-400">{rating}★</span></div>)}</div><div>{low.length ? <><h3 className="mb-2 text-sm font-medium text-amber-200">Recent low-rated queries</h3>{low.map((log) => <p key={log.id} className="border-t border-slate-800 py-2 text-sm text-slate-300">“{log.query}” <span className="text-amber-300">{log.rating}★</span></p>)}</> : <p className="text-sm text-slate-400">No low-rated queries to investigate.</p>}</div></div>;
}

function TriggerWords({ words, onAdd, onRemove }: { words: TriggerWord[]; onAdd: (word: string) => Promise<void>; onRemove: (word: string) => Promise<void> }) {
  const [word, setWord] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); if (!word.trim()) return; try { await onAdd(word.trim()); setWord(""); setError(""); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not add word"); } }
  return <div><form className="mb-3 flex gap-2" onSubmit={submit}><input aria-label="New trigger word" value={word} onChange={(event) => setWord(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" placeholder="Add a trigger word" /><button className="rounded-lg bg-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950">Add</button></form>{error && <p className="mb-2 text-sm text-rose-300">{error}</p>}{words.length ? <div className="flex flex-wrap gap-2">{words.map((item) => <span key={item.word} className="inline-flex items-center gap-1 rounded-full bg-slate-800 py-1 pl-3 pr-1 text-sm text-slate-200">{item.word}<button aria-label={`Remove ${item.word}`} onClick={() => void onRemove(item.word)} className="rounded-full px-2 text-slate-400 hover:bg-slate-700 hover:text-white">×</button></span>)}</div> : <Empty>No trigger words yet.</Empty>}</div>;
}

function JournalInventory({ journals, onInspect }: { journals: Journal[]; onInspect: (journal: Journal) => void }) {
  if (!journals.length) return <Empty>No ingested voice journals yet. Ingest an audio memo to see its source, labels, and chunks here.</Empty>;
  return <div className="space-y-3">{journals.map((journal) => <article key={journal.source_file} className="rounded-lg border border-slate-800 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-medium text-slate-100">{journal.journal_name}</h3><p className="mt-1 text-xs text-slate-400">{formatDate(journal.recorded_start)}{journal.recorded_end && journal.recorded_end !== journal.recorded_start ? ` – ${formatDate(journal.recorded_end)}` : ""} · {journal.chunk_count} chunks</p></div><button onClick={() => onInspect(journal)} className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-cyan-200">Inspect context</button></div><p className="mt-3 text-xs text-slate-400">{[...journal.labels, ...journal.tags].length ? [...journal.labels, ...journal.tags].join(" · ") : "No labels or tags yet"}</p></article>)}</div>;
}

function JournalContext({ journal, chunks, onClose }: { journal: Journal | null; chunks: JournalChunk[]; onClose: () => void }) {
  if (!journal) return null;
  return <div className="fixed inset-0 z-10 overflow-y-auto bg-slate-950/90 p-5"><section className="mx-auto max-w-3xl rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl"><div className="mb-4 flex justify-between gap-3"><div><h2 className="text-xl font-semibold">{journal.journal_name}</h2><p className="text-sm text-slate-400">Source context · {journal.chunk_count} chunks</p></div><button onClick={onClose} className="rounded bg-slate-800 px-3 py-1 text-sm">Close</button></div><div className="space-y-3">{chunks.length ? chunks.map((chunk) => <article key={chunk.id} className="rounded-lg border border-slate-800 p-4"><p className="mb-2 text-xs text-cyan-300">Chunk {(chunk.chunk_index ?? 0) + 1}{formatOffset(chunk.audio_offset) ? ` · ${formatOffset(chunk.audio_offset)}` : ""}</p><p className="whitespace-pre-wrap text-sm text-slate-200">{chunk.content}</p></article>) : <Empty>Loading journal context…</Empty>}</div></section></div>;
}

function ActionQueue({ actions, extracting, onExtract, onReview }: { actions: JournalAction[]; extracting: boolean; onExtract: () => Promise<void>; onReview: (id: string, status: "approved" | "dismissed") => Promise<void> }) {
  const suggested = actions.filter((item) => item.status === "suggested");
  return <div><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-400">Suggestions stay in this dashboard until you review them. Approval never creates an external task.</p><button onClick={() => void onExtract()} disabled={extracting} className="rounded-lg bg-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-60">{extracting ? "Extracting…" : "Extract suggestions"}</button></div>{suggested.length ? <div className="space-y-3">{suggested.map((item) => <article key={item.id} className="rounded-lg border border-amber-900/70 bg-amber-950/20 p-4"><p className="font-medium text-slate-100">{item.wording}</p><blockquote className="mt-2 border-l-2 border-amber-400 pl-3 text-sm text-slate-300">{item.evidence}</blockquote><p className="mt-2 text-xs text-slate-500">Source: {item.source_file}</p><div className="mt-3 flex gap-2"><button onClick={() => void onReview(item.id, "approved")} className="rounded bg-emerald-400 px-3 py-1 text-sm font-semibold text-slate-950">Approve</button><button onClick={() => void onReview(item.id, "dismissed")} className="rounded bg-slate-700 px-3 py-1 text-sm">Dismiss</button></div></article>)}</div> : <Empty>No suggestions waiting for review. Run extraction after voice journals have been ingested.</Empty>}</div>;
}

export default function App() {
  const [entries, setEntries] = useState<Entry[]>([]); const [logs, setLogs] = useState<RetrievalLog[]>([]); const [words, setWords] = useState<TriggerWord[]>([]); const [journals, setJournals] = useState<Journal[]>([]); const [actions, setActions] = useState<JournalAction[]>([]);
  const [state, setState] = useState<LoadState>("loading"); const [error, setError] = useState(""); const [range, setRange] = useState<Range>("30");
  const [query, setQuery] = useState(""); const [results, setResults] = useState<Entry[]>([]); const [searching, setSearching] = useState(false); const [selectedJournal, setSelectedJournal] = useState<Journal | null>(null); const [journalChunks, setJournalChunks] = useState<JournalChunk[]>([]); const [extracting, setExtracting] = useState(false);
  async function load() { setState("loading"); try { const [allEntries, allLogs, allWords, allJournals, allActions] = await Promise.all([dashboardApi.entries(), dashboardApi.logs(), dashboardApi.triggerWords(), dashboardApi.journals(), dashboardApi.journalActions()]); setEntries(allEntries); setLogs(allLogs); setWords(allWords); setJournals(allJournals); setActions(allActions); setState("ready"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not reach the API"); setState("error"); } }
  useEffect(() => { void load(); }, []);
  async function search(event: FormEvent) { event.preventDefault(); if (!query.trim()) return; setSearching(true); try { setResults((await dashboardApi.search(query.trim())).results); } catch (reason) { setError(reason instanceof Error ? reason.message : "Search failed"); } finally { setSearching(false); } }
  const visibleEntries = entries.filter((entry) => withinRange(entry, range)); const happy = entries.filter((entry) => entry.moment_type === "happy_moment");
  if (state === "loading") return <main className="p-10 text-slate-300">Loading personal knowledge base…</main>;
  if (state === "error") return <main className="mx-auto max-w-xl p-10"><h1 className="text-2xl font-bold">Dashboard unavailable</h1><p className="mt-3 text-slate-400">{error}. Start FastAPI on http://localhost:8000 and reload.</p><button className="mt-5 rounded bg-cyan-400 px-4 py-2 font-semibold text-slate-950" onClick={() => void load()}>Retry</button></main>;
  return <main className="mx-auto max-w-7xl p-5 md:p-8"><header className="mb-8 flex flex-wrap items-end justify-between gap-3"><div><p className="text-sm font-medium uppercase tracking-widest text-cyan-300">Personal knowledge base</p><h1 className="text-3xl font-bold tracking-tight">Your full brain view</h1></div><p className="text-sm text-slate-400">{entries.length} entries · live API data</p></header>{error && <p className="mb-4 rounded bg-rose-950 p-3 text-rose-200">{error}</p>}<div className="mb-5 grid gap-5 lg:grid-cols-2"><Panel title="Voice journal inventory"><JournalInventory journals={journals} onInspect={(journal) => { setSelectedJournal(journal); setJournalChunks([]); dashboardApi.journalContext(journal.source_file).then(setJournalChunks).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load journal context")); }} /></Panel><Panel title="Action suggestions for review"><ActionQueue actions={actions} extracting={extracting} onExtract={async () => { setExtracting(true); try { await dashboardApi.extractJournalActions(); setActions(await dashboardApi.journalActions()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not extract suggestions"); } finally { setExtracting(false); } }} onReview={async (id, status) => { try { const updated = await dashboardApi.reviewJournalAction(id, status); setActions((current) => current.map((item) => item.id === id ? updated : item)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not review suggestion"); } }} /></Panel></div><div className="grid gap-5 lg:grid-cols-2"><Panel title="Live retrieval search"><form onSubmit={search} className="flex gap-2"><input value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2" placeholder="Search your past thoughts" /><button className="rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950">{searching ? "Searching…" : "Search"}</button></form><div className="mt-4 space-y-3">{results.length ? results.map((entry, index) => <article key={entry.id} className="rounded-lg border border-slate-800 p-3"><div className="mb-1 flex justify-between gap-3 text-xs text-slate-400"><span>#{index + 1} · {entry.source_file ?? entry.source_type} · {formatDate(entry.recorded_at)}</span>{formatOffset(entry.audio_offset) && <a className="text-cyan-300 underline" href={dashboardApi.audioUrl(entry.id, entry.audio_offset!)}>{formatOffset(entry.audio_offset)} into {entry.source_file ?? "audio"}</a>}</div><p className="max-h-[4.5rem] overflow-hidden text-sm text-slate-200">{entry.content}</p><p className="mt-2 text-xs text-slate-400">{entry.mood ?? "unlabelled"} · {(entry.tags ?? []).join(", ")}</p></article>) : <Empty>Search to see ranked recall results.</Empty>}</div></Panel><Panel title="Mood trends"><div className="mb-4 flex gap-2">{(["30", "90", "all"] as Range[]).map((value) => <button key={value} onClick={() => setRange(value)} className={`rounded px-3 py-1 text-sm ${range === value ? "bg-cyan-400 text-slate-950" : "bg-slate-800 text-slate-300"}`}>{value === "all" ? "All time" : `${value} days`}</button>)}</div><MoodTrend entries={visibleEntries} /></Panel><Panel title="Topic distribution"><TopicDistribution entries={entries} /></Panel><Panel title="Retrieval evaluation"><EvalMetrics logs={logs} /></Panel><Panel title="Happy moments gallery"><div className="grid gap-3 sm:grid-cols-2">{happy.length ? happy.map((entry) => <article id={`entry-${entry.id}`} key={entry.id} className="rounded-lg bg-gradient-to-br from-fuchsia-950 to-slate-800 p-4"><p className="text-sm text-slate-100">{entry.visual_context || entry.content}</p><p className="mt-4 text-xs text-fuchsia-200">{formatDate(entry.recorded_at)} · {entry.mood ?? "unlabelled"}</p></article>) : <Empty>No entries are tagged happy_moment yet.</Empty>}</div></Panel><Panel title="Trigger word manager"><TriggerWords words={words} onAdd={async (word) => { await dashboardApi.addTriggerWord(word); setWords(await dashboardApi.triggerWords()); }} onRemove={async (word) => { try { await dashboardApi.removeTriggerWord(word); setWords((current) => current.filter((item) => item.word !== word)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not remove word"); } }} /></Panel></div><JournalContext journal={selectedJournal} chunks={journalChunks} onClose={() => setSelectedJournal(null)} /></main>;
}

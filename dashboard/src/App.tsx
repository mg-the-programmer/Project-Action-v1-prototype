import { FormEvent, useEffect, useMemo, useState } from "react";
import { dashboardApi, Entry, RetrievalLog, TriggerWord } from "./api";

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
  return <div className="space-y-3">{rows.map(([date, counts]) => <div key={date} className="grid grid-cols-[5.5rem_1fr] gap-3 text-xs"><span className="pt-1 text-slate-400">{date}</span><div className="flex h-6 overflow-hidden rounded bg-slate-800">{moods.map((mood) => counts[mood] ? <span key={mood} title={`${mood}: ${counts[mood]}`} style={{ width: `${(counts[mood] / max) * 100}%`, backgroundColor: moodColors[mood] }} /> : null)}</div></div>)}</div>;
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

export default function App() {
  const [entries, setEntries] = useState<Entry[]>([]); const [logs, setLogs] = useState<RetrievalLog[]>([]); const [words, setWords] = useState<TriggerWord[]>([]);
  const [state, setState] = useState<LoadState>("loading"); const [error, setError] = useState(""); const [range, setRange] = useState<Range>("30");
  const [query, setQuery] = useState(""); const [results, setResults] = useState<Entry[]>([]); const [searching, setSearching] = useState(false);
  async function load() { setState("loading"); try { const [allEntries, allLogs, allWords] = await Promise.all([dashboardApi.entries(), dashboardApi.logs(), dashboardApi.triggerWords()]); setEntries(allEntries); setLogs(allLogs); setWords(allWords); setState("ready"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not reach the API"); setState("error"); } }
  useEffect(() => { void load(); }, []);
  async function search(event: FormEvent) { event.preventDefault(); if (!query.trim()) return; setSearching(true); try { setResults((await dashboardApi.search(query.trim())).results); } catch (reason) { setError(reason instanceof Error ? reason.message : "Search failed"); } finally { setSearching(false); } }
  const visibleEntries = entries.filter((entry) => withinRange(entry, range)); const happy = entries.filter((entry) => entry.moment_type === "happy_moment");
  if (state === "loading") return <main className="p-10 text-slate-300">Loading personal knowledge base…</main>;
  if (state === "error") return <main className="mx-auto max-w-xl p-10"><h1 className="text-2xl font-bold">Dashboard unavailable</h1><p className="mt-3 text-slate-400">{error}. Start FastAPI on http://localhost:8000 and reload.</p><button className="mt-5 rounded bg-cyan-400 px-4 py-2 font-semibold text-slate-950" onClick={() => void load()}>Retry</button></main>;
  return <main className="mx-auto max-w-7xl p-5 md:p-8"><header className="mb-8 flex flex-wrap items-end justify-between gap-3"><div><p className="text-sm font-medium uppercase tracking-widest text-cyan-300">Personal knowledge base</p><h1 className="text-3xl font-bold tracking-tight">Your full brain view</h1></div><p className="text-sm text-slate-400">{entries.length} entries · live API data</p></header>{error && <p className="mb-4 rounded bg-rose-950 p-3 text-rose-200">{error}</p>}<div className="grid gap-5 lg:grid-cols-2"><Panel title="Live retrieval search"><form onSubmit={search} className="flex gap-2"><input value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2" placeholder="Search your past thoughts" /><button className="rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950">{searching ? "Searching…" : "Search"}</button></form><div className="mt-4 space-y-3">{results.length ? results.map((entry, index) => <article key={entry.id} className="rounded-lg border border-slate-800 p-3"><div className="mb-1 flex justify-between gap-3 text-xs text-slate-400"><span>#{index + 1} · {entry.source_file ?? entry.source_type} · {formatDate(entry.recorded_at)}</span>{formatOffset(entry.audio_offset) && <a className="text-cyan-300 underline" href={`#entry-${entry.id}`}>{formatOffset(entry.audio_offset)} into {entry.source_file ?? "audio"}</a>}</div><p className="max-h-[4.5rem] overflow-hidden text-sm text-slate-200">{entry.content}</p><p className="mt-2 text-xs text-slate-400">{entry.mood ?? "unlabelled"} · {(entry.tags ?? []).join(", ")}</p></article>) : <Empty>Search to see ranked recall results.</Empty>}</div></Panel><Panel title="Mood trends"><div className="mb-4 flex gap-2">{(["30", "90", "all"] as Range[]).map((value) => <button key={value} onClick={() => setRange(value)} className={`rounded px-3 py-1 text-sm ${range === value ? "bg-cyan-400 text-slate-950" : "bg-slate-800 text-slate-300"}`}>{value === "all" ? "All time" : `${value} days`}</button>)}</div><MoodTrend entries={visibleEntries} /><p className="mt-4 flex flex-wrap gap-2 text-xs text-slate-400">{moods.map((mood) => <span key={mood} className="capitalize">{mood}</span>)}</p></Panel><Panel title="Topic distribution"><TopicDistribution entries={entries} /></Panel><Panel title="Retrieval evaluation"><EvalMetrics logs={logs} /></Panel><Panel title="Happy moments gallery"><div className="grid gap-3 sm:grid-cols-2">{happy.length ? happy.map((entry) => <article id={`entry-${entry.id}`} key={entry.id} className="rounded-lg bg-gradient-to-br from-fuchsia-950 to-slate-800 p-4"><p className="text-sm text-slate-100">{entry.visual_context || entry.content}</p><p className="mt-4 text-xs text-fuchsia-200">{formatDate(entry.recorded_at)} · {entry.mood ?? "unlabelled"}</p></article>) : <Empty>No entries are tagged happy_moment yet.</Empty>}</div></Panel><Panel title="Trigger word manager"><TriggerWords words={words} onAdd={async (word) => { await dashboardApi.addTriggerWord(word); setWords(await dashboardApi.triggerWords()); }} onRemove={async (word) => { try { await dashboardApi.removeTriggerWord(word); setWords((current) => current.filter((item) => item.word !== word)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not remove word"); } }} /></Panel></div></main>;
}

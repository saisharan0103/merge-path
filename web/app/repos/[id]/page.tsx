"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, postJson } from "@/lib/api";

const TABS = [
  "Overview", "Health", "Code Map", "PR Patterns", "No-Brainers", "Issues", "PRs", "Strategy", "Logs",
] as const;
type Tab = typeof TABS[number];

export default function RepoDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [tab, setTab] = useState<Tab>("Overview");
  const qc = useQueryClient();
  const repo = useQuery({ queryKey: ["repo", id], queryFn: () => api<any>(`/repos/${id}`) });

  const pause = useMutation({
    mutationFn: () => postJson(`/repos/${id}/pause`, { reason: "user paused" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repo", id] }),
  });
  const resume = useMutation({
    mutationFn: () => postJson(`/repos/${id}/resume`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repo", id] }),
  });
  const rescan = useMutation({
    mutationFn: () => postJson(`/repos/${id}/rescan`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repo", id] }),
  });

  if (repo.isLoading) return <p>Loading…</p>;
  if (repo.isError) return <p className="text-oxblood">Repo not found.</p>;
  const r = repo.data;

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl">
          {r.upstream.owner}/{r.upstream.name}
        </h1>
        <div className="flex gap-2">
          <button className="btn secondary" onClick={() => rescan.mutate()}>Rescan</button>
          {r.paused ? (
            <button className="btn" onClick={() => resume.mutate()}>Resume</button>
          ) : (
            <button className="btn secondary" onClick={() => pause.mutate()}>Pause</button>
          )}
        </div>
      </div>
      <div className="text-sm text-gray-600">
        Fork: {r.fork.owner}/{r.fork.name} {r.fork.verified && <span className="badge green ml-2">verified</span>}
      </div>

      <div className="flex gap-2 border-b border-edge">
        {TABS.map((t) => (
          <button
            key={t}
            className={`px-3 py-2 text-sm border-b-2 ${tab === t ? "border-ink text-ink" : "border-transparent text-gray-600"}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && <Overview r={r} />}
      {tab === "Health" && <HealthTab id={id} verdict={r.health_verdict} score={r.health_score} />}
      {tab === "Code Map" && <ScanTab id={id} />}
      {tab === "PR Patterns" && <PatternsTab id={id} />}
      {tab === "No-Brainers" && <NoBrainersTab id={id} />}
      {tab === "Issues" && <IssuesTab id={id} />}
      {tab === "PRs" && <PRsTab id={id} />}
      {tab === "Strategy" && <StrategyTab id={id} />}
      {tab === "Logs" && <LogsTab id={id} />}
    </div>
  );
}

function Overview({ r }: { r: any }) {
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div className="card">
        <h3 className="font-serif text-lg mb-2">Health</h3>
        <p className="text-sm">Score: {r.health_score ?? "—"}</p>
        <p className="text-sm">Verdict: {r.health_verdict ?? "—"}</p>
        <p className="text-sm">Phase: {r.current_phase}</p>
      </div>
      <div className="card">
        <h3 className="font-serif text-lg mb-2">Profile</h3>
        <p className="text-sm">Language: {r.profile?.primary_language ?? "—"}</p>
        <p className="text-sm">Tech: {(r.profile?.tech_stack || []).join(", ") || "—"}</p>
        {(r.profile?.test_commands || []).length > 0 && (
          <p className="text-sm font-mono">{r.profile.test_commands[0]}</p>
        )}
      </div>
      <div className="card">
        <h3 className="font-serif text-lg mb-2">PR patterns</h3>
        <p className="text-sm">Sample size: {r.pr_patterns?.sample_size ?? "—"}</p>
        <p className="text-sm">Title pattern: {r.pr_patterns?.title_pattern ?? "—"}</p>
        <p className="text-sm">% with tests: {r.pr_patterns?.pct_with_tests != null ? `${(r.pr_patterns.pct_with_tests * 100).toFixed(0)}%` : "—"}</p>
      </div>
      <div className="card">
        <h3 className="font-serif text-lg mb-2">Strategy</h3>
        <p className="text-sm">Verdict: {r.strategy?.current_verdict ?? "—"}</p>
        <p className="text-sm">Reason: {r.strategy?.reason ?? "—"}</p>
      </div>
    </div>
  );
}

function HealthTab({ id }: { id: string; verdict?: string | null; score?: number | null }) {
  const q = useQuery({ queryKey: ["health", id], queryFn: () => api<any>(`/repos/${id}/health`) });
  if (q.isLoading) return <p>Loading…</p>;
  if (!q.data?.current) return <p className="text-sm text-gray-500">No signals yet.</p>;
  const c = q.data.current;
  return (
    <div className="card">
      <table>
        <tbody>
          {Object.entries(c).map(([k, v]) => (
            <tr key={k}>
              <td className="font-mono text-xs">{k}</td>
              <td>{v == null ? "—" : String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScanTab({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["scan", id], queryFn: () => api<any>(`/repos/${id}/scan`) });
  if (q.isLoading) return <p>Loading…</p>;
  if (q.isError) return <p className="text-sm text-gray-500">No scan yet.</p>;
  const s = q.data;
  return (
    <div className="card space-y-2 text-sm font-mono">
      <p>Total files: {s.total_files}</p>
      <p>Source dirs: {(s.source_dirs || []).join(", ")}</p>
      <p>Entrypoints: {(s.entrypoints || []).slice(0, 8).join(", ")}</p>
      <p>Test files: {(s.test_files || []).slice(0, 8).join(", ")}</p>
      <p>Config files: {(s.config_files || []).slice(0, 8).join(", ")}</p>
    </div>
  );
}

function PatternsTab({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["patterns", id], queryFn: () => api<any>(`/repos/${id}/pr-patterns`) });
  if (q.isLoading) return <p>Loading…</p>;
  if (q.isError) return <p className="text-sm text-gray-500">No patterns yet.</p>;
  return (
    <div className="card">
      <table>
        <tbody>
          {Object.entries(q.data).map(([k, v]) => (
            <tr key={k}><td className="font-mono text-xs">{k}</td><td>{Array.isArray(v) ? (v as any).join(", ") : String(v)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NoBrainersTab({ id }: { id: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["nobrainers", id], queryFn: () => api<any>(`/repos/${id}/no-brainers`) });
  const approve = useMutation({
    mutationFn: (nb_id: number) => postJson(`/no-brainers/${nb_id}/approve`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nobrainers", id] }),
  });
  const skip = useMutation({
    mutationFn: (nb_id: number) => postJson(`/no-brainers/${nb_id}/skip`, { reason: "user" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nobrainers", id] }),
  });
  if (q.isLoading) return <p>Loading…</p>;
  if (!q.data?.items?.length) return <p className="text-sm text-gray-500">No items detected yet.</p>;
  return (
    <table>
      <thead>
        <tr><th>Type</th><th>Summary</th><th>Confidence</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        {q.data.items.map((n: any) => (
          <tr key={n.id}>
            <td className="font-mono">{n.type}</td>
            <td>{n.summary}</td>
            <td>{(n.confidence * 100).toFixed(0)}%</td>
            <td><span className="badge gray">{n.status}</span></td>
            <td>
              {n.status === "detected" && (
                <div className="flex gap-2">
                  <button className="btn" onClick={() => approve.mutate(n.id)}>Approve</button>
                  <button className="btn secondary" onClick={() => skip.mutate(n.id)}>Skip</button>
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function IssuesTab({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["issues", id], queryFn: () => api<any>(`/repos/${id}/issues`) });
  if (q.isLoading) return <p>Loading…</p>;
  if (!q.data?.items?.length) return <p className="text-sm text-gray-500">No issues detected.</p>;
  return (
    <table>
      <thead>
        <tr><th>#</th><th>Title</th><th>Score</th><th>Verdict</th><th>Status</th></tr>
      </thead>
      <tbody>
        {q.data.items.map((i: any) => (
          <tr key={i.id}>
            <td>{i.github_number}</td>
            <td><Link href={`/issues/${i.id}`} className="underline">{i.title}</Link></td>
            <td>{i.score}</td>
            <td>{i.eligibility_verdict}</td>
            <td><span className="badge gray">{i.status}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PRsTab({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["prs", id], queryFn: () => api<any>(`/prs?repo_id=${id}`) });
  if (q.isLoading) return <p>Loading…</p>;
  if (!q.data?.items?.length) return <p className="text-sm text-gray-500">No PRs yet.</p>;
  return (
    <table>
      <thead><tr><th>#</th><th>Title</th><th>Type</th><th>Status</th><th>Buffer until</th></tr></thead>
      <tbody>
        {q.data.items.map((p: any) => (
          <tr key={p.id}>
            <td><Link href={`/prs/${p.id}`} className="underline">{p.upstream_pr_number ?? p.id}</Link></td>
            <td>{p.title}</td>
            <td>{p.type}</td>
            <td>{p.status}</td>
            <td className="font-mono text-xs">{p.buffer_until ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function StrategyTab({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["strategy", id], queryFn: () => api<any>(`/repos/${id}/strategy`) });
  if (q.isLoading) return <p>Loading…</p>;
  if (q.isError) return <p className="text-sm text-gray-500">No strategy yet.</p>;
  return (
    <div className="card">
      <p>Verdict: <strong>{q.data.current_verdict}</strong></p>
      <p>Reason: {q.data.reason}</p>
      <p>Next action: {q.data.next_action}</p>
      {q.data.history?.length > 0 && (
        <div className="mt-4">
          <h4 className="font-serif">History</h4>
          <ul className="font-mono text-xs">
            {q.data.history.slice(-10).map((h: any, idx: number) => (
              <li key={idx}>{h.at} → {h.verdict}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function LogsTab({ id }: { id: string }) {
  const q = useQuery({
    queryKey: ["repo-runs", id],
    queryFn: () => api<any>(`/runs?repo_id=${id}&page_size=20`),
  });
  if (q.isLoading) return <p>Loading…</p>;
  if (!q.data?.items?.length) return <p className="text-sm text-gray-500">No runs yet.</p>;
  return (
    <table>
      <thead><tr><th>Run</th><th>Kind</th><th>Stage</th><th>Status</th></tr></thead>
      <tbody>
        {q.data.items.map((r: any) => (
          <tr key={r.id}>
            <td><Link href={`/runs/${r.id}`} className="underline">{r.id}</Link></td>
            <td>{r.kind}</td>
            <td className="font-mono text-xs">{r.stage}</td>
            <td>{r.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

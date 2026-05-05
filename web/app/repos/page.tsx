"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, postJson } from "@/lib/api";
import type { Page, Repo } from "@/lib/types";

export default function ReposPage() {
  const [open, setOpen] = useState(false);
  const repos = useQuery({
    queryKey: ["repos"],
    queryFn: () => api<Page<Repo>>("/repos?page=1&page_size=100"),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl">Repositories</h1>
        <button className="btn" onClick={() => setOpen(true)}>Add repo</button>
      </div>

      {repos.isLoading && <p>Loading…</p>}
      {repos.isError && <p className="text-oxblood">Failed to load</p>}
      {repos.data?.items.length === 0 && (
        <div className="card text-sm text-gray-600">No repositories yet — click <strong>Add repo</strong>.</div>
      )}

      {repos.data && repos.data.items.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Repo</th><th>Lang</th><th>Stars</th><th>Health</th>
              <th>Phase</th><th>Open PRs</th><th>Merged</th><th>Merge rate</th><th>Paused</th>
            </tr>
          </thead>
          <tbody>
            {repos.data.items.map((r) => (
              <tr key={r.id}>
                <td>
                  <Link href={`/repos/${r.id}`} className="underline">
                    {r.upstream.owner}/{r.upstream.name}
                  </Link>
                </td>
                <td>{r.language ?? "—"}</td>
                <td>{r.stars ?? "—"}</td>
                <td>
                  {r.health_score == null ? "—" : (
                    <span className={`badge ${r.health_verdict === "alive" ? "green" : r.health_verdict === "stale" ? "red" : "gray"}`}>
                      {r.health_score} · {r.health_verdict}
                    </span>
                  )}
                </td>
                <td>{r.current_phase}</td>
                <td>{r.open_pr_count ?? 0}</td>
                <td>{r.merged_pr_count ?? 0}</td>
                <td>{r.merge_rate == null ? "—" : `${(r.merge_rate * 100).toFixed(0)}%`}</td>
                <td>{r.paused ? <span className="badge red">paused</span> : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {open && <AddRepoModal onClose={() => setOpen(false)} />}
    </div>
  );
}

function AddRepoModal({ onClose }: { onClose: () => void }) {
  const [upstream, setUpstream] = useState("");
  const [fork, setFork] = useState("");
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => postJson<Repo>("/repos", { upstream_url: upstream, fork_url: fork }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["repos"] });
      onClose();
    },
    onError: (e: any) => {
      const msg = e?.body?.detail?.message || e?.body?.detail?.error || e.message;
      setError(typeof msg === "string" ? msg : "Failed");
    },
  });

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center" onClick={onClose}>
      <div className="card w-[440px]" onClick={(e) => e.stopPropagation()}>
        <h2 className="font-serif text-xl mb-4">Add repository</h2>
        <p className="text-xs text-gray-600 mb-4">
          Enter both URLs. The agent verifies your fork is a fork of the upstream.
        </p>
        <label className="text-xs uppercase tracking-wide text-gray-600">Upstream URL</label>
        <input className="input mb-3" placeholder="https://github.com/owner/repo"
               value={upstream} onChange={(e) => setUpstream(e.target.value)} />
        <label className="text-xs uppercase tracking-wide text-gray-600">Your fork URL</label>
        <input className="input mb-3" placeholder="https://github.com/yourname/repo"
               value={fork} onChange={(e) => setFork(e.target.value)} />
        {error && <div className="text-oxblood text-sm mb-3">{error}</div>}
        <div className="flex justify-end gap-2 mt-2">
          <button className="btn secondary" onClick={onClose}>Cancel</button>
          <button className="btn" onClick={() => m.mutate()} disabled={m.isPending || !upstream || !fork}>
            {m.isPending ? "Adding…" : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}

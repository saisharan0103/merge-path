"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Page, Repo } from "@/lib/types";

export default function StrategyPage() {
  const summary = useQuery({ queryKey: ["strategy-summary"], queryFn: () => api<any>("/strategy/summary") });
  const repos = useQuery({ queryKey: ["repos"], queryFn: () => api<Page<Repo>>("/repos?page_size=100") });

  if (summary.isLoading || repos.isLoading) return <p>Loading…</p>;
  const s = summary.data!;
  const items = repos.data?.items ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl">Strategy</h1>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {(["green", "yellow", "red", "blacklist"] as const).map((k) => (
          <div key={k} className="card">
            <div className="text-xs uppercase tracking-wider text-gray-500">{k}</div>
            <div className="text-2xl font-serif">{s[k]}</div>
          </div>
        ))}
        <div className="card">
          <div className="text-xs uppercase tracking-wider text-gray-500">cooldown queue</div>
          <div className="text-2xl font-serif">{s.cooldown_queue_size}</div>
        </div>
      </div>

      <table>
        <thead><tr><th>Repo</th><th>Phase</th><th>Verdict</th><th>Cooldown until</th><th>Paused</th></tr></thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              <td><Link href={`/repos/${r.id}`} className="underline">{r.upstream.owner}/{r.upstream.name}</Link></td>
              <td>{r.current_phase}</td>
              <td>
                <span className={`badge ${r.health_verdict === "alive" ? "green" : r.health_verdict === "stale" ? "red" : "gray"}`}>
                  {r.health_verdict ?? "—"}
                </span>
              </td>
              <td className="font-mono text-xs">—</td>
              <td>{r.paused ? <span className="badge red">paused</span> : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

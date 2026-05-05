"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Page, PR } from "@/lib/types";

export default function PRsPage() {
  const [view, setView] = useState<"all" | "byrepo">("all");
  const q = useQuery({ queryKey: ["prs"], queryFn: () => api<Page<PR>>("/prs?page_size=100") });

  if (q.isLoading) return <p>Loading…</p>;
  const items = q.data?.items ?? [];

  if (!items.length) return <p className="text-sm text-gray-500">No PRs yet.</p>;

  const grouped: Record<string, PR[]> = {};
  for (const p of items) {
    const key = String(p.repo_id);
    grouped[key] = grouped[key] || [];
    grouped[key].push(p);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl">Pull requests</h1>
        <div className="flex gap-2">
          <button className={`btn ${view === "all" ? "" : "secondary"}`} onClick={() => setView("all")}>All</button>
          <button className={`btn ${view === "byrepo" ? "" : "secondary"}`} onClick={() => setView("byrepo")}>By repo</button>
        </div>
      </div>

      {view === "all" ? (
        <table>
          <thead><tr><th>#</th><th>Title</th><th>Type</th><th>Status</th><th>Score</th><th>Buffer</th></tr></thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id}>
                <td><Link href={`/prs/${p.id}`} className="underline">{p.upstream_pr_number ?? p.id}</Link></td>
                <td>{p.title}</td>
                <td>{p.type}</td>
                <td>{p.status}</td>
                <td>{p.latest_traction?.traction_score ?? 0}</td>
                <td className="font-mono text-xs">{p.buffer_until ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([repoId, list]) => (
            <div key={repoId}>
              <h3 className="font-serif text-lg mb-2">Repo {repoId}</h3>
              <table>
                <thead><tr><th>#</th><th>Title</th><th>Status</th></tr></thead>
                <tbody>
                  {list.map((p) => (
                    <tr key={p.id}>
                      <td><Link href={`/prs/${p.id}`} className="underline">{p.upstream_pr_number ?? p.id}</Link></td>
                      <td>{p.title}</td>
                      <td>{p.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

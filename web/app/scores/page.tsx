"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Page, Repo } from "@/lib/types";

export default function ScoresPage() {
  const q = useQuery({
    queryKey: ["repos-scored"],
    queryFn: () => api<Page<Repo>>("/repos?page=1&page_size=100&sort=health_score:desc"),
  });
  if (q.isLoading) return <p>Loading…</p>;
  const rows = q.data?.items ?? [];
  if (!rows.length) return <p className="text-sm text-gray-500">No repos yet.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl">Scores leaderboard</h1>
      <table>
        <thead><tr><th>Rank</th><th>Repo</th><th>Health</th><th>Verdict</th><th>Lang</th></tr></thead>
        <tbody>
          {rows
            .filter((r) => r.health_score != null)
            .sort((a, b) => (b.health_score ?? 0) - (a.health_score ?? 0))
            .map((r, idx) => (
              <tr key={r.id}>
                <td>{idx + 1}</td>
                <td>
                  <Link href={`/repos/${r.id}`} className="underline">
                    {r.upstream.owner}/{r.upstream.name}
                  </Link>
                </td>
                <td>{r.health_score}</td>
                <td>{r.health_verdict}</td>
                <td>{r.language ?? "—"}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

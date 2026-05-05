"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Page, Repo, Issue } from "@/lib/types";

export default function IssuesPage() {
  const repos = useQuery({ queryKey: ["repos"], queryFn: () => api<Page<Repo>>("/repos") });

  const issues = useQuery({
    queryKey: ["all-issues", repos.data?.items.map((r) => r.id).join(",")],
    enabled: !!repos.data,
    queryFn: async () => {
      const out: (Issue & { repo: string })[] = [];
      for (const r of repos.data!.items) {
        const p = await api<Page<Issue>>(`/repos/${r.id}/issues?page_size=100`);
        for (const i of p.items) out.push({ ...i, repo: `${r.upstream.owner}/${r.upstream.name}` });
      }
      return out;
    },
  });

  if (repos.isLoading) return <p>Loading…</p>;
  const rows = issues.data ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl">Issues</h1>
      {rows.length === 0 ? (
        <p className="text-sm text-gray-500">No issues yet.</p>
      ) : (
        <table>
          <thead><tr><th>Repo</th><th>#</th><th>Title</th><th>Score</th><th>Verdict</th><th>Status</th></tr></thead>
          <tbody>
            {rows.sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).map((i) => (
              <tr key={i.id}>
                <td className="font-mono text-xs">{i.repo}</td>
                <td>{i.github_number}</td>
                <td><Link href={`/issues/${i.id}`} className="underline">{i.title}</Link></td>
                <td>{i.score}</td>
                <td>{i.eligibility_verdict}</td>
                <td>{i.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

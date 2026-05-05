"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function PRDetail() {
  const { id } = useParams<{ id: string }>();
  const q = useQuery({ queryKey: ["pr", id], queryFn: () => api<any>(`/prs/${id}`) });

  if (q.isLoading) return <p>Loading…</p>;
  if (q.isError) return <p>PR not found.</p>;
  const p = q.data;
  const series = (p.traction_history ?? []).map((h: any, idx: number) => ({
    idx,
    score: h.traction_score,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl">{p.title || `PR ${p.id}`}</h1>
      <p className="text-sm text-gray-600">
        {p.repo?.upstream?.owner}/{p.repo?.upstream?.name}
        {p.upstream_url && <> · <a className="underline" href={p.upstream_url} target="_blank">GitHub #{p.upstream_pr_number}</a></>}
      </p>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="font-serif text-lg mb-2">Status</h3>
          <p className="text-sm">{p.status}</p>
          <p className="text-sm">Branch: <span className="font-mono">{p.fork_branch_name}</span></p>
          <p className="text-sm">Files: {p.files_changed_count} · +{p.loc_added}/-{p.loc_removed}</p>
          <p className="text-sm">Buffer until: <span className="font-mono text-xs">{p.buffer_until ?? "—"}</span></p>
          <p className="text-sm">Grace until: <span className="font-mono text-xs">{p.grace_until ?? "—"}</span></p>
        </div>

        <div className="card">
          <h3 className="font-serif text-lg mb-2">Traction</h3>
          {series.length === 0 ? (
            <p className="text-sm text-gray-500">No data yet.</p>
          ) : (
            <div style={{ height: 200 }}>
              <ResponsiveContainer>
                <LineChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="idx" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#1E3A8A" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {p.body && (
        <div className="card">
          <h3 className="font-serif text-lg mb-2">PR body</h3>
          <pre className="font-mono text-xs whitespace-pre-wrap">{p.body}</pre>
        </div>
      )}
    </div>
  );
}

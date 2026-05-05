"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import Link from "next/link";

type Overview = {
  total_repos: number;
  active_repos: number;
  total_prs: number;
  open_prs: number;
  merged_prs: number;
  closed_prs: number;
  merge_rate: number;
  verdict_distribution: Record<string, number>;
};

type Funnel = {
  issues_detected: number;
  issues_eligible: number;
  issues_reproduced: number;
  issues_fixed: number;
  prs_opened: number;
  prs_merged: number;
};

const COLORS = { green: "#2D5016", yellow: "#A07800", red: "#7C2D12", blacklist: "#222" };

export default function Dashboard() {
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => api<Overview>("/metrics/overview") });
  const funnel = useQuery({ queryKey: ["funnel"], queryFn: () => api<Funnel>("/metrics/funnel") });
  const recent = useQuery({
    queryKey: ["activity-recent"],
    queryFn: () => api<{ items: { id: number; kind: string; status: string; stage: string | null; started_at: string | null }[] }>("/activity?page=1&page_size=10"),
  });

  if (overview.isLoading) return <p>Loading…</p>;
  if (overview.isError) return <p className="text-oxblood">Failed to load.</p>;
  const o = overview.data!;
  const pieData = Object.entries(o.verdict_distribution).map(([k, v]) => ({ name: k, value: v }));

  return (
    <div className="space-y-8">
      <h1 className="text-2xl">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Total repos" value={o.total_repos} />
        <Stat label="Active repos" value={o.active_repos} />
        <Stat label="Open PRs" value={o.open_prs} />
        <Stat label="Merge rate" value={o.merge_rate ? `${(o.merge_rate * 100).toFixed(0)}%` : "—"} />
      </div>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="font-serif text-lg mb-4">Verdict distribution</h3>
          {pieData.every((d) => d.value === 0) ? (
            <p className="text-sm text-gray-500">No repos yet.</p>
          ) : (
            <div style={{ height: 220 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={pieData} dataKey="value" outerRadius={80} label>
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={COLORS[entry.name as keyof typeof COLORS] || "#888"} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="card">
          <h3 className="font-serif text-lg mb-4">Funnel</h3>
          {funnel.data ? (
            <ul className="text-sm space-y-1 font-mono">
              <li>issues detected: {funnel.data.issues_detected}</li>
              <li>issues eligible: {funnel.data.issues_eligible}</li>
              <li>issues reproduced: {funnel.data.issues_reproduced}</li>
              <li>issues fixed: {funnel.data.issues_fixed}</li>
              <li>PRs opened: {funnel.data.prs_opened}</li>
              <li>PRs merged: {funnel.data.prs_merged}</li>
            </ul>
          ) : (
            <p>—</p>
          )}
        </div>
      </section>

      <section className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-serif text-lg">Recent activity</h3>
          <Link href="/activity" className="text-sm underline">View all</Link>
        </div>
        {recent.data && recent.data.items.length ? (
          <table>
            <thead>
              <tr><th>ID</th><th>Kind</th><th>Stage</th><th>Status</th><th>Started</th></tr>
            </thead>
            <tbody>
              {recent.data.items.map((r) => (
                <tr key={r.id}>
                  <td><Link href={`/runs/${r.id}`} className="underline">{r.id}</Link></td>
                  <td>{r.kind}</td>
                  <td className="font-mono text-xs">{r.stage ?? "—"}</td>
                  <td><StatusBadge status={r.status} /></td>
                  <td className="font-mono text-xs">{r.started_at ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-gray-500">No runs yet. Add a repo to begin.</p>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wider text-gray-500">{label}</div>
      <div className="text-2xl font-serif mt-1">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "succeeded" ? "green" :
    status === "running" || status === "pending" ? "navy" :
    status === "failed" || status === "abandoned" || status === "cancelled" ? "red" : "gray";
  return <span className={`badge ${cls}`}>{status}</span>;
}

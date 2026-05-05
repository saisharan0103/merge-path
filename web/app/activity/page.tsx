"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function ActivityPage() {
  const q = useQuery({
    queryKey: ["activity"],
    queryFn: () => api<any>("/activity?page=1&page_size=50"),
  });
  if (q.isLoading) return <p>Loading…</p>;
  const items = q.data?.items ?? [];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl">Activity</h1>
      {items.length === 0 ? (
        <p className="text-sm text-gray-500">No activity yet.</p>
      ) : (
        <table>
          <thead><tr><th>Run</th><th>Kind</th><th>Stage</th><th>Status</th><th>Started</th><th>Finished</th></tr></thead>
          <tbody>
            {items.map((r: any) => (
              <tr key={r.id}>
                <td><Link href={`/runs/${r.id}`} className="underline">{r.id}</Link></td>
                <td>{r.kind}</td>
                <td className="font-mono text-xs">{r.stage}</td>
                <td>{r.status}</td>
                <td className="font-mono text-xs">{r.started_at}</td>
                <td className="font-mono text-xs">{r.finished_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

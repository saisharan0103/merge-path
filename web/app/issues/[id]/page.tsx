"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api, postJson } from "@/lib/api";

export default function IssueDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["issue", id], queryFn: () => api<any>(`/issues/${id}`) });
  const skip = useMutation({
    mutationFn: () => postJson(`/issues/${id}/skip`, { reason: "user" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["issue", id] }),
  });
  const retry = useMutation({
    mutationFn: () => postJson(`/issues/${id}/retry`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["issue", id] }),
  });

  if (q.isLoading) return <p>Loading…</p>;
  if (q.isError) return <p>Issue not found.</p>;
  const i = q.data;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl">#{i.github_number} — {i.title}</h1>
          <p className="text-sm text-gray-600">
            Status: <span className="badge gray">{i.status}</span>
            {i.github_url && <> · <a href={i.github_url} className="underline" target="_blank">GitHub</a></>}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={() => retry.mutate()}>Retry</button>
          <button className="btn secondary" onClick={() => skip.mutate()}>Skip</button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="font-serif text-lg mb-2">Score: {i.score}</h3>
          {i.score_breakdown && Object.keys(i.score_breakdown).length > 0 && (
            <table>
              <tbody>
                {Object.entries(i.score_breakdown).map(([k, v]) => (
                  <tr key={k}><td className="font-mono text-xs">{k}</td><td>{String(v)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="text-sm mt-2">Verdict: {i.eligibility_verdict}</p>
          {i.filter_reason && <p className="text-sm">Filter reason: {i.filter_reason}</p>}
        </div>

        <div className="card">
          <h3 className="font-serif text-lg mb-2">Reproduction</h3>
          <p className="text-sm">Confidence: {i.reproducibility_confidence ?? "—"}</p>
          {i.reproduction_log && (
            <pre className="font-mono text-xs whitespace-pre-wrap mt-2 max-h-60 overflow-auto">{i.reproduction_log}</pre>
          )}
        </div>
      </div>

      {i.fix_plan && (
        <div className="card">
          <h3 className="font-serif text-lg mb-2">Fix plan</h3>
          <p className="text-sm">Root cause: {i.fix_plan.root_cause}</p>
          <p className="text-sm">Approach: {i.fix_plan.approach}</p>
          <p className="text-sm">Target files: {(i.fix_plan.target_files || []).join(", ")}</p>
        </div>
      )}

      {i.latest_patch && (
        <div className="card">
          <h3 className="font-serif text-lg mb-2">Patch</h3>
          <p className="text-sm">+{i.latest_patch.loc_added} / -{i.latest_patch.loc_removed}</p>
          <pre className="font-mono text-xs whitespace-pre-wrap mt-2 max-h-72 overflow-auto">{i.latest_patch.diff_text}</pre>
        </div>
      )}

      {i.comment && (
        <div className="card">
          <h3 className="font-serif text-lg mb-2">Issue comment</h3>
          <p className="text-sm">Status: {i.comment.status}</p>
          {i.comment.posted_url && <a href={i.comment.posted_url} className="underline">View on GitHub</a>}
        </div>
      )}

      {i.pr && (
        <div className="card">
          <h3 className="font-serif text-lg mb-2">Pull request</h3>
          <p className="text-sm">#{i.pr.upstream_pr_number} — {i.pr.status}</p>
          {i.pr.upstream_url && <a href={i.pr.upstream_url} className="underline">View on GitHub</a>}
        </div>
      )}

      <div className="card">
        <h3 className="font-serif text-lg mb-2">Body</h3>
        <pre className="font-mono text-xs whitespace-pre-wrap">{i.body}</pre>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, putJson } from "@/lib/api";

export default function SettingsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api<any>("/settings") });
  const [pat, setPat] = useState("");
  const [bm, setBm] = useState("");
  const [pauseAll, setPauseAll] = useState<boolean | null>(null);

  const savePat = useMutation({
    mutationFn: () => putJson("/settings/pat", { github_pat: pat }),
    onSuccess: () => {
      setPat("");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });
  const saveSettings = useMutation({
    mutationFn: () => {
      const body: any = {};
      if (bm) body.buffer_multiplier = Number(bm);
      if (pauseAll !== null) body.pause_all = pauseAll;
      return putJson("/settings", body);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  if (q.isLoading) return <p>Loading…</p>;
  const s = q.data;

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl">Settings</h1>

      <div className="card">
        <h3 className="font-serif text-lg mb-3">GitHub PAT</h3>
        <p className="text-sm mb-2">
          PAT is set: <span className="badge gray">{s.github_pat_set ? "yes" : "no"}</span>{" "}
          {s.github_username && <>· user: <strong>{s.github_username}</strong></>}
        </p>
        <input className="input mb-3" placeholder="ghp_..." value={pat} onChange={(e) => setPat(e.target.value)} />
        <button className="btn" onClick={() => savePat.mutate()} disabled={!pat || savePat.isPending}>
          {savePat.isPending ? "Saving…" : "Save PAT"}
        </button>
        {savePat.isError && <p className="text-oxblood text-sm mt-2">Failed to save PAT.</p>}
      </div>

      <div className="card">
        <h3 className="font-serif text-lg mb-3">Pipeline tuning</h3>
        <p className="text-sm">Buffer multiplier: {s.buffer_multiplier}</p>
        <input className="input mb-3" placeholder="2.0" value={bm} onChange={(e) => setBm(e.target.value)} />
        <p className="text-sm">Max concurrent runs: {s.max_concurrent_runs}</p>
        <p className="text-sm">Min health score: {s.min_health_score}</p>
        <label className="text-sm flex items-center gap-2 mt-2">
          <input type="checkbox" checked={pauseAll ?? s.pause_all}
                 onChange={(e) => setPauseAll(e.target.checked)} />
          Pause all
        </label>
        <button className="btn mt-3" onClick={() => saveSettings.mutate()}>Save</button>
      </div>

      <div className="card">
        <h3 className="font-serif text-lg mb-3">Codex</h3>
        <p className="text-sm">Binary: <span className="font-mono">{s.codex_binary}</span></p>
        <p className="text-sm">Healthy: <span className={`badge ${s.codex_healthy ? "green" : "red"}`}>{s.codex_healthy ? "yes" : "no"}</span></p>
      </div>
    </div>
  );
}

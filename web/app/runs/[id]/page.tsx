"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

type Log = { id?: number; ts?: string; level?: string; stage?: string; message?: string };

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [logs, setLogs] = useState<Log[]>([]);
  const [done, setDone] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const run = useQuery({ queryKey: ["run", id], queryFn: () => api<any>(`/runs/${id}`), refetchInterval: 4000 });

  useEffect(() => {
    if (!id) return;
    const es = new EventSource(`/api/v1/runs/${id}/stream`);
    es.addEventListener("log", (e) => {
      try {
        const ev = JSON.parse((e as MessageEvent).data);
        setLogs((prev) => [...prev, ev]);
      } catch {}
    });
    es.addEventListener("end", () => {
      setDone(true);
      es.close();
    });
    es.onerror = () => {
      es.close();
    };
    return () => es.close();
  }, [id]);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl">Run #{id}</h1>
      {run.data && (
        <div className="card">
          <p className="text-sm">Kind: {run.data.kind}</p>
          <p className="text-sm">Stage: <span className="font-mono">{run.data.stage}</span></p>
          <p className="text-sm">Status: <span className="badge gray">{run.data.status}</span></p>
          {run.data.error && <p className="text-sm text-oxblood">Error: {run.data.error}</p>}
          {run.data.abandon_reason && <p className="text-sm text-oxblood">Abandoned: {run.data.abandon_reason}</p>}
        </div>
      )}

      <div className="card">
        <h3 className="font-serif text-lg mb-2">Live logs {done && <span className="text-xs text-gray-500">(stream ended)</span>}</h3>
        <div ref={ref} className="font-mono text-xs whitespace-pre-wrap max-h-[60vh] overflow-auto bg-black/3">
          {logs.map((l, idx) => (
            <div key={idx} className="border-b border-edge/40 py-1">
              <span className="text-gray-500">{l.ts?.slice(11, 19)}</span>{" "}
              <span className="text-navy">{l.stage ?? "—"}</span>{" "}
              <span className={l.level === "warn" ? "text-oxblood" : l.level === "error" ? "text-oxblood font-bold" : ""}>
                {l.message}
              </span>
            </div>
          ))}
          {logs.length === 0 && <div className="text-gray-500">Waiting for log events…</div>}
        </div>
      </div>
    </div>
  );
}

# Log Streaming

## Recommendation: SSE for live runs, polling for everything else

Simplest approach that doesn't suck:
- **Server-Sent Events (SSE)** for the run detail page (live tailing)
- **Plain REST polling** (every 5–10s) for list views like `/runs`, `/prs`, `/dashboard`
- Logs are persisted to Postgres (so reload doesn't lose history)

No WebSockets. No GraphQL subscriptions. Just SSE which is HTTP and trivial in FastAPI.

## How it works

### Producer side (Celery worker)

Worker emits log events to two places simultaneously:

```python
# app/log_bus.py
import json, redis
from datetime import datetime

r = redis.Redis(...)

def emit_log(run_id: int, level: str, message: str, stage: str = None):
    event = {
        "run_id": run_id,
        "ts": datetime.utcnow().isoformat(),
        "level": level,            # info | warn | error
        "stage": stage,
        "message": message,
    }
    # 1. publish to redis pubsub for live SSE subscribers
    r.publish(f"runs:{run_id}", json.dumps(event))
    # 2. async insert into Postgres for history
    db_insert_log_event(event)
```

### Consumer side (FastAPI SSE endpoint)

```python
# app/api/runs.py
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
import asyncio, redis.asyncio as aioredis

router = APIRouter()

@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: int, request: Request):
    async def event_gen():
        # 1. send any buffered logs from DB first (so user sees history on connect)
        for old in fetch_logs(run_id, limit=200):
            yield {"event": "log", "data": json.dumps(old)}

        # 2. subscribe to redis pubsub for new logs
        client = aioredis.Redis(...)
        pubsub = client.pubsub()
        await pubsub.subscribe(f"runs:{run_id}")

        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    yield {"event": "log", "data": msg["data"]}
                # also poll run status; if terminal, send "end" and break
                run = await get_run(run_id)
                if run.status in ("succeeded", "failed", "abandoned", "cancelled"):
                    yield {"event": "end", "data": json.dumps({"status": run.status})}
                    break
        finally:
            await pubsub.unsubscribe(f"runs:{run_id}")
            await client.close()

    return EventSourceResponse(event_gen())
```

### Frontend

```typescript
// hooks/useRunStream.ts
export function useRunStream(runId: number) {
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [status, setStatus] = useState<string>("running");

  useEffect(() => {
    const es = new EventSource(`/api/v1/runs/${runId}/stream`);
    es.addEventListener("log", (e) => {
      const event = JSON.parse(e.data);
      setLogs((prev) => [...prev, event]);
    });
    es.addEventListener("end", (e) => {
      setStatus(JSON.parse(e.data).status);
      es.close();
    });
    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);

  return { logs, status };
}
```

## Polling for non-live views

`/dashboard`, `/prs`, `/repos`, `/runs` (list) — frontend uses React Query with 5–10s stale time.

```typescript
useQuery(["dashboard"], fetchDashboard, { refetchInterval: 10_000 });
```

No need for live push on these.

## Persistence model

`log_events` table:
```sql
log_events (
  id BIGSERIAL,
  run_id BIGINT REFERENCES pipeline_runs(id),
  ts TIMESTAMPTZ DEFAULT now(),
  level VARCHAR(8),       -- info | warn | error
  stage VARCHAR(40),
  message TEXT,
  meta JSONB              -- optional structured payload
);
CREATE INDEX ON log_events(run_id, ts);
```

Retention: 90 days, then archive/drop via cron.

## Reconnect behavior

If SSE connection drops:
- EventSource auto-reconnects after 3s by default
- On reconnect, FastAPI resends buffered logs (last 200) — duplicates are deduped client-side by `(ts, message)` hash

## Why not WebSockets

- WS adds bidirectional needs we don't have
- WS is harder to load-balance (sticky sessions)
- WS requires more deps and connection management
- SSE works over plain HTTP, easy through any proxy

## Why not just polling for live too

- Polling at 1s for live logs floods the API
- Logs feel laggy (chunked by interval)
- SSE delivers events in <100ms after emit

## Rate limit on the SSE endpoint

Max 5 concurrent SSE connections per user. Rejected with 429 if exceeded. (Frontend should only open one at a time anyway.)

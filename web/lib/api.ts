// Tiny fetch wrapper. The Next.js rewrite proxies /api/v1/* to the backend.

const BASE = "/api/v1";

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!r.ok) {
    let body: unknown = null;
    try {
      body = await r.json();
    } catch {
      // ignore
    }
    const err = new Error(`API ${r.status}`) as Error & { status: number; body: unknown };
    err.status = r.status;
    err.body = body;
    throw err;
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export async function postJson<T = unknown>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export async function putJson<T = unknown>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

export async function del(path: string): Promise<void> {
  await api(path, { method: "DELETE" });
}

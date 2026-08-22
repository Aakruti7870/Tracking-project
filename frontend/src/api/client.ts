// API client for TrackMyRMC. Base URL from env; all routes under /api.
const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

export type ApiError = { status: number; detail: string };

async function handle<T>(res: Response): Promise<T> {
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const detail =
      (body && (body.detail || body.message)) || `Request failed (${res.status})`;
    throw { status: res.status, detail } as ApiError;
  }
  return body as T;
}

export async function requestOtp(identifier: string) {
  const res = await fetch(`${BASE}/auth/request-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier }),
  });
  return handle<{
    status: string;
    channel: string;
    expires_in: number;
    dev_otp?: string;
    delivery: { adapter: string; configured: boolean };
  }>(res);
}

export async function verifyOtp(identifier: string, code: string) {
  const res = await fetch(`${BASE}/auth/verify-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, code }),
  });
  return handle<{
    access_token: string;
    token_type: string;
    expires_at: string;
    role: string;
    name: string;
  }>(res);
}

export async function apiGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handle<T>(res);
}

export async function apiPost<T>(path: string, token: string, body?: any): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return handle<T>(res);
}

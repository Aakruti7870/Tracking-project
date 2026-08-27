// API client for TrackMyRMC. Base URL from env; all routes under /api.
const RAW_BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL?.trim();

function apiBase(): string {
  if (!RAW_BACKEND) {
    throw {
      status: 0,
      detail: "TrackMyRMC backend is not configured for this build",
    } as ApiError;
  }
  return `${RAW_BACKEND.replace(/\/$/, "")}/api`;
}

export type ApiError = { status: number; detail: string };

export type AuthSessionResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  role: string;
  name: string;
};

export type PlayReviewRole = "customer" | "plant_owner" | "authority" | "driver";

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

function authHeaders(token: string) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function apiPublicGet<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`);
  return handle<T>(res);
}

export async function apiPublicPost<T>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function requestOtp(identifier: string) {
  return apiPublicPost<{
    status: string;
    channel: string;
    expires_in: number;
    dev_otp?: string;
    delivery: { adapter: string; configured: boolean };
  }>("/auth/request-otp", { identifier });
}

export async function verifyOtp(identifier: string, code: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/verify-otp", { identifier, code });
}

export async function playReviewLogin(role: PlayReviewRole, accessCode: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/play-review", {
    role,
    access_code: accessCode,
  });
}

export async function startGoogleStaffLogin() {
  return apiPublicGet<{ authorization_url: string }>("/auth/google/start");
}

export async function exchangeGoogleStaffCode(code: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/google/exchange", { code });
}

export async function apiGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handle<T>(res);
}

export async function apiPost<T>(path: string, token: string, body?: any): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: authHeaders(token),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function apiPut<T>(path: string, token: string, body?: any): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function apiPatch<T>(path: string, token: string, body?: any): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function apiDelete<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  return handle<T>(res);
}
const base = (import.meta.env.VITE_API_URL || "http://localhost:8000/api").replace(/\/$/, "");
export type AdminUser = { id: string; name: string; email: string | null; role: "central_admin"; role_label: string };
export type Home = { kpis: { label: string; value: number }[] };
async function response<T>(res: Response): Promise<T> { if (!res.ok) throw new Error(res.status === 401 ? "Authentication failed." : "Request could not be completed."); return res.json() as Promise<T>; }
const headers = (token?: string) => ({ "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) });
export function post<T>(path: string, body?: object, token?: string) { return fetch(`${base}${path}`, { method: "POST", headers: headers(token), body: JSON.stringify(body || {}) }).then(response<T>); }
export function patch<T>(path: string, body?: object, token?: string) { return fetch(`${base}${path}`, { method: "PATCH", headers: headers(token), body: JSON.stringify(body || {}) }).then(response<T>); }
export function get<T>(path: string, token: string) { return fetch(`${base}${path}`, { headers: { Authorization: `Bearer ${token}` } }).then(response<T>); }

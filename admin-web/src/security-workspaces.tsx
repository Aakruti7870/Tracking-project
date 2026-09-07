import { type FormEvent, useEffect, useMemo, useState } from "react";
import { get, patch, post } from "./api";

type AdminAccess = {
  id: string | null; email: string; name: string | null; enabled: boolean; root_identity: boolean;
  permissions: string[] | null; effective_permissions: string[]; mfa_enabled: boolean; status: string;
};
type AdminAccessResponse = { admins: AdminAccess[]; available_permissions: string[] };

type SessionRow = {
  id: string; administrator: string; created_at?: string; last_activity_at?: string; auth_surface: string;
  mfa_provenance: boolean; expires_at?: string; device_summary?: string | null; revoked: boolean;
  revoke_reason?: string | null; is_current: boolean;
};

type CaseMessage = { message: string; author: string; internal: boolean; created_at?: string };
type SupportCase = { id: string; case_number: string; category: string; status: string; created_at?: string; updated_at?: string; messages: CaseMessage[] };

const when = (value?: string) => value ? new Date(value).toLocaleString() : "—";

export function PermissionsWorkspace({ token, stepUpFresh, requestStepUp }: { token: string; stepUpFresh: boolean; requestStepUp(): void }) {
  const [data, setData] = useState<AdminAccessResponse>();
  const [target, setTarget] = useState<AdminAccess>();
  const [selected, setSelected] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => { try { setData(await get<AdminAccessResponse>("/control-center/admin-access", token)); } catch { setError("Permission grants could not be loaded."); } };
  useEffect(() => { void load(); }, [token]);

  function edit(admin: AdminAccess) {
    setTarget(admin); setSelected(admin.permissions ?? admin.effective_permissions ?? []); setReason(""); setError("");
  }
  function toggle(permission: string) {
    setSelected((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission]);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!target) return;
    if (!stepUpFresh) { requestStepUp(); return; }
    if (reason.trim().length < 8) { setError("Enter an audit reason of at least 8 characters."); return; }
    setBusy(true); setError("");
    try {
      await post("/control-center/admin-access", { email: target.email, enabled: target.enabled, permissions: selected, reason: reason.trim() }, token);
      setTarget(undefined); setReason(""); await load();
    } catch { setError("Permission change was denied. permissions.manage, fresh MFA, and safe escalation policy are required."); }
    finally { setBusy(false); }
  }

  return <div className="moduleGrid">
    <section className="panel"><header className="panelHeader"><div><small>EXPLICIT GRANTS</small><h3>Administrator permissions</h3></div></header><div className="panelBody settingsList">
      {(data?.admins || []).map((admin) => <article key={admin.email}><div><b>{admin.email}</b><p>{admin.root_identity ? "Root administrator" : "Restricted administrator"} · {admin.effective_permissions.length} effective permission(s) · MFA {admin.mfa_enabled ? "enabled" : "not enrolled"}</p></div><button className="secondaryButton" type="button" disabled={!admin.enabled} onClick={() => edit(admin)}>Edit grants</button></article>)}
    </div></section>
    {target ? <section className="panel"><header className="panelHeader"><div><small>FRESH MFA REQUIRED</small><h3>Edit {target.email}</h3></div></header><div className="panelBody"><form onSubmit={save}>
      <div className="settingsList">{(data?.available_permissions || []).map((permission) => <label key={permission}><input type="checkbox" checked={selected.includes(permission)} onChange={() => toggle(permission)} /> {permission}</label>)}</div>
      <label htmlFor="permission-reason">Audit reason</label><textarea id="permission-reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} />
      {error && <div className="errorBanner" role="alert">{error}</div>}
      <div className="dialogActions"><button type="button" className="secondaryButton" onClick={() => setTarget(undefined)}>Cancel</button><button className="primaryButton" disabled={busy}>{busy ? "Saving…" : "Save grants"}</button></div>
    </form></div></section> : null}
  </div>;
}

export function SessionsWorkspace({ token, stepUpFresh, requestStepUp, onCurrentRevoked }: { token: string; stepUpFresh: boolean; requestStepUp(): void; onCurrentRevoked(): void }) {
  const [rows, setRows] = useState<SessionRow[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const load = async () => { try { setRows((await get<{ sessions: SessionRow[] }>("/control-center/sessions", token)).sessions || []); } catch { setError("Administrator sessions could not be loaded."); } };
  useEffect(() => { void load(); }, [token]);
  async function revoke(row: SessionRow) {
    if (!stepUpFresh) { requestStepUp(); return; }
    if (reason.trim().length < 8) { setError("Enter an audit reason of at least 8 characters before revoking a session."); return; }
    setBusy(row.id); setError("");
    try { await post(`/control-center/sessions/${row.id}/revoke`, { reason: reason.trim() }, token); if (row.is_current) onCurrentRevoked(); else { setReason(""); await load(); } }
    catch { setError("Session revocation was denied or the session is already inactive."); }
    finally { setBusy(""); }
  }
  return <section className="portalWorkspaceCard"><header className="workspaceHeader"><div><small>SAFE SESSION METADATA</small><h3>Administrator sessions</h3><p>No bearer tokens, MFA secrets, or recovery codes are returned.</p></div><button className="secondaryButton" onClick={() => void load()}>Refresh</button></header>
    <label htmlFor="session-reason">Audit reason for revocation</label><textarea id="session-reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} />
    {error && <div className="errorBanner" role="alert">{error}</div>}
    <div className="settingsList">{rows.map((row) => <article key={row.id}><div><b>{row.administrator}</b><p>Created {when(row.created_at)} · Last activity {when(row.last_activity_at)} · {row.auth_surface} · MFA provenance {row.mfa_provenance ? "yes" : "no"} · Expires {when(row.expires_at)}{row.device_summary ? ` · ${row.device_summary}` : ""}</p></div>{row.revoked ? <span className="stateBadge">Revoked{row.revoke_reason ? ` · ${row.revoke_reason}` : ""}</span> : <button className="dangerButton" disabled={Boolean(busy)} onClick={() => void revoke(row)}>{busy === row.id ? "Revoking…" : row.is_current ? "Revoke this session" : "Revoke"}</button>}</article>)}</div>
  </section>;
}

export function SupportWorkspace({ token, stepUpFresh, requestStepUp }: { token: string; stepUpFresh: boolean; requestStepUp(): void }) {
  const [status, setStatus] = useState("OPEN");
  const [cases, setCases] = useState<SupportCase[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<SupportCase>();
  const [message, setMessage] = useState("");
  const [internal, setInternal] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = async () => { try { const result = await get<{ cases: SupportCase[] }>(`/control-center/support/cases?status=${status}`, token); setCases(result.cases || []); if (!selectedId && result.cases?.[0]) setSelectedId(result.cases[0].id); } catch { setError("Support cases could not be loaded."); } };
  useEffect(() => { void load(); }, [token, status]);
  useEffect(() => { if (!selectedId) { setSelected(undefined); return; } get<{ case: SupportCase }>(`/control-center/support/cases/${selectedId}`, token).then((value) => setSelected(value.case)).catch(() => setError("Support conversation could not be loaded.")); }, [selectedId, token]);

  async function send(event: FormEvent) {
    event.preventDefault(); if (!selected) return;
    if (!stepUpFresh) { requestStepUp(); return; }
    if (message.trim().length < 1) return;
    setBusy(true); setError("");
    try { await post(`/control-center/support/cases/${selected.id}/${internal ? "notes" : "replies"}`, { message: message.trim(), internal }, token); setMessage(""); const fresh = await get<{ case: SupportCase }>(`/control-center/support/cases/${selected.id}`, token); setSelected(fresh.case); }
    catch { setError("Support update was denied. support.manage and fresh MFA are required."); }
    finally { setBusy(false); }
  }
  async function changeStatus(next: string) {
    if (!selected) return; if (!stepUpFresh) { requestStepUp(); return; }
    setBusy(true); setError("");
    try { await patch(`/control-center/support/cases/${selected.id}/status`, { status: next }, token); setSelected({ ...selected, status: next }); await load(); }
    catch { setError("Status update was denied."); }
    finally { setBusy(false); }
  }

  const visibleMessages = useMemo(() => selected?.messages || [], [selected]);
  return <div className="moduleGrid"><section className="panel"><header className="panelHeader"><div><small>AUDITED SUPPORT</small><h3>Cases</h3></div><select value={status} onChange={(event) => setStatus(event.target.value)}>{["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"].map((item) => <option key={item}>{item}</option>)}</select></header><div className="panelBody settingsList">{cases.map((item) => <article key={item.id}><div><b>{item.case_number}</b><p>{item.category} · {item.status} · {when(item.updated_at || item.created_at)}</p></div><button className="secondaryButton" onClick={() => setSelectedId(item.id)}>Open</button></article>)}</div></section>
    <section className="panel"><header className="panelHeader"><div><small>CONVERSATION</small><h3>{selected?.case_number || "Select a case"}</h3></div></header><div className="panelBody">{error && <div className="errorBanner" role="alert">{error}</div>}{visibleMessages.map((item, index) => <article key={`${item.created_at || index}-${index}`}><b>{item.internal ? "Internal note" : item.author}</b><p>{item.message}</p><small>{when(item.created_at)}</small></article>)}{selected ? <form onSubmit={send}><label><input type="checkbox" checked={internal} onChange={(event) => setInternal(event.target.checked)} /> Internal note</label><textarea value={message} onChange={(event) => setMessage(event.target.value)} maxLength={1000} placeholder={internal ? "Internal context" : "Public reply"} /><div className="dialogActions"><button className="primaryButton" disabled={busy || !message.trim()}>{busy ? "Sending…" : internal ? "Add internal note" : "Send public reply"}</button>{["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"].filter((item) => item !== selected.status).map((item) => <button type="button" className="secondaryButton" key={item} disabled={busy} onClick={() => void changeStatus(item)}>{item}</button>)}</div></form> : null}</div></section></div>;
}

export function RolesWorkspace() {
  const templates = [
    ["Root Central Admin", "Code-pinned recovery identity; legacy full permission default unless explicit grants are set."],
    ["Restricted Central Admin", "Explicit Control Center approval plus an explicit permission set; no implicit full access."],
    ["Authority", "Operational Plant Staff email/MFA role. Not a Control Center administrator."],
    ["Plant Owner / Staff", "Approved Plant Staff email OTP bootstrap followed by supported MFA/passkey flow."],
  ];
  return <section className="portalWorkspaceCard"><header className="workspaceHeader"><div><small>READ-ONLY POLICY</small><h3>Role templates</h3><p>Role mutation policy is not defined here; these templates describe current authentication boundaries.</p></div></header><div className="settingsList">{templates.map(([name, detail]) => <article key={name}><div><b>{name}</b><p>{detail}</p></div><span className="stateBadge">Read only</span></article>)}</div></section>;
}

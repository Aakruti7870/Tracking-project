import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { get, post } from "./api";

type ReviewerState = {
  enabled: boolean; requested_enabled: boolean; credential_configured: boolean; credential_supported: boolean;
  credential_migration_required: boolean; source: string; updated_at: string | null; reviewer_accounts: number;
  active_sessions: number; roles: string[];
};

type AdminAccess = {
  id: string | null; email: string; name: string | null; provisioned: boolean; enabled: boolean;
  root_identity: boolean; mfa_enabled: boolean; status: string; permissions: string[] | null;
  effective_permissions: string[]; active_sessions: number; is_current: boolean;
};
type AdminAccessResponse = { admins: AdminAccess[]; available_permissions: string[] };

type OnboardingRequest = {
  id: string; request_number?: string; source?: string; name?: string; address?: string;
  applicant_owner_name?: string; applicant_email?: string; applicant_mobile?: string; status?: string;
};
type UnownedPlant = { id: string; name?: string; city?: string; address?: string; status?: string };

function Notice({ children, danger = false }: { children: ReactNode; danger?: boolean }) {
  return <div className={danger ? "errorBanner" : "runtimeNote"}>{children}</div>;
}

export function ReviewerAccessWorkspace({ token, stepUpFresh, requestStepUp }: { token: string; stepUpFresh: boolean; requestStepUp(): void }) {
  const [state, setState] = useState<ReviewerState>();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = () => get<ReviewerState>("/control-center/reviewer-access", token).then(setState).catch(() => setError("Reviewer access state could not be loaded."));
  useEffect(() => { void load(); }, [token]);

  async function setEnabled(enabled: boolean) {
    setError("");
    if (!stepUpFresh) { requestStepUp(); return; }
    if (reason.trim().length < 8) { setError("Enter an audit reason of at least 8 characters."); return; }
    setBusy(true);
    try { setState(await post<ReviewerState>("/control-center/reviewer-access", { enabled, reason: reason.trim() }, token)); setReason(""); }
    catch { setError("Reviewer access change was denied. Confirm MFA and supported server-side reviewer credential configuration."); }
    finally { setBusy(false); }
  }

  if (!state) return <section className="portalWorkspaceCard"><div className="emptyWorkspace"><h4>Reviewer Access Control</h4><p>{error || "Loading server-side reviewer controls…"}</p></div></section>;
  return <div className="moduleGrid">
    <section className="panel"><header className="panelHeader"><div><small>GOOGLE PLAY REVIEW</small><h3>Reviewer login control</h3></div><span className="stateBadge">{state.enabled ? "ENABLED" : "DISABLED"}</span></header><div className="panelBody settingsList">
      <article><div><b>Effective access</b><p>Customer, Plant Owner and Driver reviewer identities only. Turning access off revokes every isolated reviewer session.</p></div><span className="stateBadge">{state.enabled ? "On" : "Off"}</span></article>
      <article><div><b>Reviewer credential</b><p>The credential remains server-side and is never displayed here.</p></div><span className="stateBadge">{state.credential_supported ? "Supported" : state.credential_configured ? "Migration required" : "Missing"}</span></article>
      {state.credential_migration_required ? <Notice danger>Reviewer Access remains disabled until the existing server credential is migrated to the supported six-digit format. The current value is not exposed or rotated automatically.</Notice> : null}
      <article><div><b>{state.active_sessions} active reviewer sessions</b><p>{state.roles.join(" · ")} · {state.reviewer_accounts} isolated accounts</p></div><span className="stateBadge">Revocable</span></article>
    </div></section>
    <section className="panel"><header className="panelHeader"><div><small>HIGH-RISK CONTROL</small><h3>Change reviewer access</h3></div></header><div className="panelBody"><label htmlFor="review-reason">Audit reason</label><textarea id="review-reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} />{error && <div className="errorBanner" role="alert">{error}</div>}<div className="dialogActions"><button className="secondaryButton" disabled={busy || state.enabled || !state.credential_supported} onClick={() => void setEnabled(true)}>Enable reviewer access</button><button className="dangerButton" disabled={busy || !state.enabled} onClick={() => void setEnabled(false)}>Disable & revoke sessions</button></div>{!stepUpFresh ? <Notice>Fresh Authenticator verification is required.</Notice> : null}</div></section>
  </div>;
}

export function AdminAccessWorkspace({ token, stepUpFresh, requestStepUp }: { token: string; stepUpFresh: boolean; requestStepUp(): void }) {
  const [data, setData] = useState<AdminAccessResponse>();
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [approvalPermissions, setApprovalPermissions] = useState<string[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const load = () => get<AdminAccessResponse>("/control-center/admin-access", token).then(setData).catch(() => setError("Approved administrator identities could not be loaded."));
  useEffect(() => { void load(); }, [token]);
  const toggle = (permission: string) => setApprovalPermissions((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission]);

  async function change(admin: AdminAccess, enabled: boolean) {
    if (!stepUpFresh) { requestStepUp(); return; }
    if (reason.trim().length < 8) { setError("Enter an audit reason of at least 8 characters."); return; }
    setBusy(admin.email); setError("");
    try {
      const body: Record<string, unknown> = { email: admin.email, enabled, reason: reason.trim() };
      if (enabled && !admin.root_identity) body.permissions = admin.permissions ?? [];
      await post("/control-center/admin-access", body, token); setReason(""); await load();
    } catch { setError("Administrator access change was denied by role, MFA, permission, or final-root safeguards."); }
    finally { setBusy(""); }
  }

  async function approveNew() {
    if (!stepUpFresh) { requestStepUp(); return; }
    if (reason.trim().length < 8) { setError("Enter an audit reason of at least 8 characters."); return; }
    if (!email.trim()) return;
    setBusy(email); setError("");
    try { await post("/control-center/admin-access", { email: email.trim().toLowerCase(), enabled: true, permissions: approvalPermissions, reason: reason.trim() }, token); setEmail(""); setReason(""); setApprovalPermissions([]); await load(); }
    catch { setError("Approval was denied. The email must already be provisioned specifically as Central Admin; existing Customer, Owner, Authority or Staff identities are never converted here."); }
    finally { setBusy(""); }
  }

  const admins = data?.admins || [];
  return <div className="moduleGrid">
    <section className="panel"><header className="panelHeader"><div><small>APPROVED EMAILS</small><h3>Central Admin identities</h3></div><span className="stateBadge">{admins.filter((item) => item.enabled).length} enabled</span></header><div className="panelBody settingsList">{admins.map((admin) => <article key={admin.email}><div><b>{admin.email}</b><p>{admin.name || "Awaiting provisioning"} · MFA {admin.mfa_enabled ? "enabled" : "not enrolled"} · {admin.active_sessions} web session(s) · {admin.effective_permissions?.length || 0} effective grant(s)</p></div><div className="dialogActions">{admin.root_identity ? <span className="stateBadge">Root</span> : <span className="stateBadge">Restricted</span>}{admin.enabled ? <button className="dangerButton" disabled={Boolean(busy) || admin.is_current} onClick={() => void change(admin, false)}>{admin.is_current ? "Current identity" : "Suspend"}</button> : <button className="secondaryButton" disabled={Boolean(busy) || !admin.provisioned} onClick={() => void change(admin, true)}>Enable</button>}</div></article>)}</div></section>
    <section className="panel"><header className="panelHeader"><div><small>ADDITIONAL APPROVAL</small><h3>Approve an existing Central Admin</h3></div></header><div className="panelBody"><p>This screen never changes another account's role. Provisioning as <code>central_admin</code> must already exist.</p><label htmlFor="approved-admin-email">Central Admin email</label><input id="approved-admin-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /><label>Initial explicit permission set</label><div className="settingsList">{(data?.available_permissions || []).map((permission) => <label key={permission}><input type="checkbox" checked={approvalPermissions.includes(permission)} onChange={() => toggle(permission)} /> {permission}</label>)}</div><label htmlFor="admin-reason">Audit reason</label><textarea id="admin-reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} />{error && <div className="errorBanner" role="alert">{error}</div>}<button className="primaryButton" disabled={Boolean(busy) || !email.trim()} onClick={() => void approveNew()}>Approve email with grants</button>{!stepUpFresh ? <Notice>Fresh Authenticator verification is required.</Notice> : null}</div></section>
  </div>;
}

export function OwnerAccessWorkspace({ token, stepUpFresh, requestStepUp }: { token: string; stepUpFresh: boolean; requestStepUp(): void }) {
  const [requests, setRequests] = useState<OnboardingRequest[]>([]);
  const [plants, setPlants] = useState<UnownedPlant[]>([]);
  const [plantId, setPlantId] = useState("");
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(""); const [error, setError] = useState("");
  const load = async () => { try { const [pending, unowned] = await Promise.all([get<{ requests: OnboardingRequest[] }>("/control-center/owners/requests", token), get<{ plants: UnownedPlant[] }>("/control-center/owners/unowned-plants", token)]); setRequests(pending.requests || []); setPlants(unowned.plants || []); setPlantId((current) => current || unowned.plants?.[0]?.id || ""); } catch { setError("Plant Owner access data could not be loaded."); } };
  useEffect(() => { void load(); }, [token]);

  async function approve(request: OnboardingRequest) { if (!stepUpFresh) { requestStepUp(); return; } setBusy(request.id); setError(""); try { await post(`/control-center/owners/requests/${request.id}/approve`, {}, token); await load(); } catch { setError("Owner approval was denied by permission, fresh-MFA, identity-conflict, or plant-state safeguards."); } finally { setBusy(""); } }
  async function assign(event: FormEvent) { event.preventDefault(); if (!stepUpFresh) { requestStepUp(); return; } if (!plantId || name.trim().length < 2 || !email.trim()) { setError("Select a plant and enter Owner name and approved email."); return; } setBusy("assign-owner"); setError(""); try { await post(`/control-center/owners/plants/${plantId}/assign`, { name: name.trim(), email: email.trim().toLowerCase(), phone: phone.trim() || null }, token); setName(""); setEmail(""); setPhone(""); await load(); } catch { setError("Owner assignment failed. Existing Customer, Driver, Authority, or Staff identities cannot be silently converted."); } finally { setBusy(""); } }
  const selfOnboarding = useMemo(() => requests.filter((item) => item.source === "self_onboarding"), [requests]);
  return <div className="moduleGrid"><section className="panel"><header className="panelHeader"><div><small>PENDING APPROVAL</small><h3>Owner onboarding requests</h3></div><span className="stateBadge">{selfOnboarding.length} pending</span></header><div className="panelBody settingsList">{selfOnboarding.length === 0 ? <Notice>No self-onboarding Owner requests are pending.</Notice> : selfOnboarding.map((request) => <article key={request.id}><div><b>{request.applicant_owner_name || "Plant Owner"} · {request.name || "RMC Plant"}</b><p>{request.applicant_email || "No email"} · {request.applicant_mobile || "No mobile"}<br />{request.address}</p></div><button className="primaryButton" disabled={Boolean(busy)} onClick={() => void approve(request)}>{busy === request.id ? "Approving…" : "Approve Owner + Plant"}</button></article>)}</div></section>
    <section className="panel"><header className="panelHeader"><div><small>OWNER ASSIGNMENT</small><h3>Assign Owner to unowned plant</h3></div></header><div className="panelBody"><form onSubmit={assign}><label htmlFor="owner-plant">Plant</label><select id="owner-plant" value={plantId} onChange={(event) => setPlantId(event.target.value)}><option value="">Select plant</option>{plants.map((plant) => <option key={plant.id} value={plant.id}>{plant.name || plant.id}{plant.city ? ` · ${plant.city}` : ""}</option>)}</select><label htmlFor="owner-name">Owner name</label><input id="owner-name" value={name} onChange={(event) => setName(event.target.value)} /><label htmlFor="owner-email">Approved Owner email</label><input id="owner-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /><label htmlFor="owner-phone">Owner mobile (optional)</label><input id="owner-phone" value={phone} onChange={(event) => setPhone(event.target.value)} />{error && <div className="errorBanner" role="alert">{error}</div>}<button className="primaryButton" disabled={Boolean(busy) || plants.length === 0}>{busy === "assign-owner" ? "Assigning…" : "Approve Owner access"}</button></form><Notice>Authority keeps the operational Plant Discovery workflow. Central Admin Owner actions use only these permission- and MFA-gated Control Center endpoints.</Notice></div></section>
  </div>;
}

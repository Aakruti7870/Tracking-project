import { type FormEvent, useEffect, useMemo, useState } from "react";
import { get, post } from "./api";

type ReviewerState = {
  enabled: boolean;
  requested_enabled: boolean;
  credential_configured: boolean;
  source: string;
  updated_at: string | null;
  reviewer_accounts: number;
  active_sessions: number;
  roles: string[];
};

type AdminAccess = {
  id: string | null;
  email: string;
  name: string | null;
  provisioned: boolean;
  enabled: boolean;
  root_identity: boolean;
  mfa_enabled: boolean;
  status: string;
  permissions: string[] | null;
  active_sessions: number;
  is_current: boolean;
};

type AdminAccessResponse = {
  admins: AdminAccess[];
  available_permissions: string[];
};

type OnboardingRequest = {
  id: string;
  request_number?: string;
  source?: string;
  name?: string;
  address?: string;
  applicant_owner_name?: string;
  applicant_email?: string;
  applicant_mobile?: string;
  status?: string;
};

type UnownedPlant = { id: string; name?: string; city?: string; address?: string; status?: string };

function Notice({ children, danger = false }: { children: React.ReactNode; danger?: boolean }) {
  return <div className={danger ? "errorBanner" : "runtimeNote"}>{children}</div>;
}

export function ReviewerAccessWorkspace({ token, stepUpFresh, requestStepUp }: { token: string; stepUpFresh: boolean; requestStepUp(): void }) {
  const [state, setState] = useState<ReviewerState>();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () => get<ReviewerState>("/control-center/reviewer-access", token).then(setState).catch(() => setError("Reviewer access state could not be loaded."));
  useEffect(load, [token]);

  async function setEnabled(enabled: boolean) {
    setError("");
    if (!stepUpFresh) { requestStepUp(); return; }
    if (reason.trim().length < 8) { setError("Enter an audit reason of at least 8 characters."); return; }
    setBusy(true);
    try {
      const next = await post<ReviewerState>("/control-center/reviewer-access", { enabled, reason: reason.trim() }, token);
      setState(next);
      setReason("");
    } catch {
      setError("Reviewer access change was denied. Confirm MFA and server reviewer credential configuration.");
    } finally { setBusy(false); }
  }

  if (!state) return <section className="portalWorkspaceCard"><div className="emptyWorkspace"><h4>Reviewer Access Control</h4><p>{error || "Loading server-side reviewer controls…"}</p></div></section>;

  return <div className="moduleGrid">
    <section className="panel">
      <header className="panelHeader"><div><small>GOOGLE PLAY REVIEW</small><h3>Reviewer login control</h3></div><span className="stateBadge">{state.enabled ? "ENABLED" : "DISABLED"}</span></header>
      <div className="panelBody settingsList">
        <article><div><b>Effective access</b><p>Controls the isolated Customer, Plant Owner and Driver reviewer accounts at the backend. Turning access off also revokes active reviewer sessions.</p></div><span className="stateBadge">{state.enabled ? "On" : "Off"}</span></article>
        <article><div><b>Reviewer credential</b><p>The credential remains server-side and is never displayed in this portal.</p></div><span className="stateBadge">{state.credential_configured ? "Configured" : "Missing"}</span></article>
        <article><div><b>Runtime source</b><p>{state.source === "control_center" ? "Last state was explicitly set from Control Center." : "Using deployment default until a Super Admin changes it."}</p></div><span className="stateBadge">{state.source}</span></article>
      </div>
    </section>

    <section className="panel">
      <header className="panelHeader"><div><small>LIVE POSTURE</small><h3>Reviewer session status</h3></div></header>
      <div className="panelBody settingsList">
        <article><div><b>{state.reviewer_accounts} isolated accounts</b><p>{state.roles.join(" · ")}</p></div><span className="stateBadge">Review only</span></article>
        <article><div><b>{state.active_sessions} active reviewer sessions</b><p>Disabling reviewer access revokes these sessions immediately.</p></div><span className="stateBadge">Revocable</span></article>
      </div>
    </section>

    <section className="panel">
      <header className="panelHeader"><div><small>HIGH-RISK CONTROL</small><h3>Change reviewer access</h3></div></header>
      <div className="panelBody">
        <label htmlFor="review-reason">Audit reason</label>
        <textarea id="review-reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} placeholder="Example: Google Play review window completed" />
        {error && <div className="errorBanner" role="alert">{error}</div>}
        <div className="dialogActions">
          <button className="secondaryButton" type="button" disabled={busy || state.enabled} onClick={() => void setEnabled(true)}>{busy ? "Applying…" : "Enable reviewer access"}</button>
          <button className="dangerButton" type="button" disabled={busy || !state.enabled} onClick={() => void setEnabled(false)}>{busy ? "Applying…" : "Disable & revoke sessions"}</button>
        </div>
        {!stepUpFresh ? <Notice>Fresh Authenticator verification is required before either change.</Notice> : null}
      </div>
    </section>
  </div>;
}

export function AdminAccessWorkspace({ token, stepUpFresh, requestStepUp }: { token: string; stepUpFresh: boolean; requestStepUp(): void }) {
  const [data, setData] = useState<AdminAccessResponse>();
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = () => get<AdminAccessResponse>("/control-center/admin-access", token).then(setData).catch(() => setError("Approved administrator identities could not be loaded."));
  useEffect(load, [token]);

  async function change(target: string, enabled: boolean) {
    setError("");
    if (!stepUpFresh) { requestStepUp(); return; }
    if (reason.trim().length < 8) { setError("Enter an audit reason of at least 8 characters."); return; }
    setBusy(target);
    try {
      await post("/control-center/admin-access", { email: target, enabled, reason: reason.trim() }, token);
      setReason("");
      setEmail("");
      await load();
    } catch {
      setError("Administrator access change was denied. The email must already belong to a Central Admin account, and you cannot disable your own current identity.");
    } finally { setBusy(""); }
  }

  const admins = data?.admins || [];
  return <div className="moduleGrid">
    <section className="panel">
      <header className="panelHeader"><div><small>APPROVED EMAILS</small><h3>Super Admin identities</h3></div><span className="stateBadge">{admins.filter((item) => item.enabled).length} enabled</span></header>
      <div className="panelBody settingsList">
        {admins.map((admin) => <article key={admin.email}>
          <div><b>{admin.email}</b><p>{admin.name || "Awaiting account provisioning"} · MFA {admin.mfa_enabled ? "enabled" : "not enrolled"} · {admin.active_sessions} active web session(s)</p></div>
          <div className="dialogActions">
            {admin.root_identity ? <span className="stateBadge">Root approved</span> : <span className="stateBadge">Additional</span>}
            {admin.enabled
              ? <button className="dangerButton" type="button" disabled={Boolean(busy) || admin.is_current} onClick={() => void change(admin.email, false)}>{busy === admin.email ? "Applying…" : admin.is_current ? "Current identity" : "Suspend"}</button>
              : <button className="secondaryButton" type="button" disabled={Boolean(busy) || !admin.provisioned} onClick={() => void change(admin.email, true)}>{busy === admin.email ? "Applying…" : "Enable"}</button>}
          </div>
        </article>)}
      </div>
    </section>

    <section className="panel">
      <header className="panelHeader"><div><small>ADDITIONAL APPROVAL</small><h3>Approve an existing Central Admin email</h3></div></header>
      <div className="panelBody">
        <p>This does not silently promote Customer, Owner, Authority or Plant Staff accounts. The email must already be provisioned with the Central Admin role.</p>
        <label htmlFor="approved-admin-email">Central Admin email</label>
        <input id="approved-admin-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="admin@example.com" />
        <label htmlFor="admin-reason">Audit reason</label>
        <textarea id="admin-reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} placeholder="Reason for approval or suspension" />
        {error && <div className="errorBanner" role="alert">{error}</div>}
        <button className="primaryButton" type="button" disabled={Boolean(busy) || !email.trim()} onClick={() => void change(email.trim().toLowerCase(), true)}>Approve email</button>
        {!stepUpFresh ? <Notice>Fresh Authenticator verification is required for access-list changes.</Notice> : null}
      </div>
    </section>

    <section className="panel">
      <header className="panelHeader"><div><small>POLICY</small><h3>Privileged login requirements</h3></div></header>
      <div className="panelBody settingsList">
        <article><div><b>Central Admin role</b><p>Other roles cannot be promoted through this screen.</p></div><span className="stateBadge">Required</span></article>
        <article><div><b>Authenticator MFA</b><p>Approved email alone never creates a privileged session.</p></div><span className="stateBadge">Required</span></article>
        <article><div><b>Web provenance</b><p>Mobile/staff sessions cannot be upgraded into Control Center sessions.</p></div><span className="stateBadge">Required</span></article>
      </div>
    </section>
  </div>;
}

export function OwnerAccessWorkspace({ token, stepUpFresh, requestStepUp }: { token: string; stepUpFresh: boolean; requestStepUp(): void }) {
  const [requests, setRequests] = useState<OnboardingRequest[]>([]);
  const [plants, setPlants] = useState<UnownedPlant[]>([]);
  const [plantId, setPlantId] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const [pending, unowned] = await Promise.all([
        get<{ requests: OnboardingRequest[] }>("/plant-discovery/requests", token),
        get<{ plants: UnownedPlant[] }>("/plant-discovery/unowned-plants", token),
      ]);
      setRequests(pending.requests || []);
      setPlants(unowned.plants || []);
      setPlantId((current) => current || unowned.plants?.[0]?.id || "");
    } catch { setError("Plant Owner access data could not be loaded."); }
  };
  useEffect(() => { void load(); }, [token]);

  async function approve(request: OnboardingRequest) {
    setError("");
    if (!stepUpFresh) { requestStepUp(); return; }
    setBusy(request.id);
    try {
      await post(`/plant-discovery/requests/${request.id}/approve`, {}, token);
      await load();
    } catch { setError("Onboarding approval failed. Review the submitted Owner identity and plant state."); }
    finally { setBusy(""); }
  }

  async function assign(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!stepUpFresh) { requestStepUp(); return; }
    if (!plantId || name.trim().length < 2 || !email.trim()) { setError("Select a plant and enter Owner name and approved email."); return; }
    setBusy("assign-owner");
    try {
      await post(`/plant-discovery/plants/${plantId}/assign-owner`, { name: name.trim(), email: email.trim().toLowerCase(), phone: phone.trim() || null }, token);
      setName(""); setEmail(""); setPhone("");
      await load();
    } catch { setError("Owner assignment failed. The email may already belong to another role or the plant may already have an Owner."); }
    finally { setBusy(""); }
  }

  const selfOnboarding = useMemo(() => requests.filter((item) => item.source === "self_onboarding"), [requests]);
  return <div className="moduleGrid">
    <section className="panel">
      <header className="panelHeader"><div><small>PENDING APPROVAL</small><h3>Owner onboarding requests</h3></div><span className="stateBadge">{selfOnboarding.length} pending</span></header>
      <div className="panelBody settingsList">
        {selfOnboarding.length === 0 ? <Notice>No self-onboarding Owner requests are pending.</Notice> : selfOnboarding.map((request) => <article key={request.id}>
          <div><b>{request.applicant_owner_name || "Plant Owner"} · {request.name || "RMC Plant"}</b><p>{request.applicant_email || "No email"} · {request.applicant_mobile || "No mobile"}<br />{request.address}</p></div>
          <button className="primaryButton" type="button" disabled={Boolean(busy)} onClick={() => void approve(request)}>{busy === request.id ? "Approving…" : "Approve Owner + Plant"}</button>
        </article>)}
      </div>
    </section>

    <section className="panel">
      <header className="panelHeader"><div><small>OWNER ASSIGNMENT</small><h3>Add approved Owner email to an unowned plant</h3></div></header>
      <div className="panelBody">
        <form onSubmit={assign}>
          <label htmlFor="owner-plant">Plant</label>
          <select id="owner-plant" value={plantId} onChange={(event) => setPlantId(event.target.value)} required>
            <option value="">Select plant</option>
            {plants.map((plant) => <option key={plant.id} value={plant.id}>{plant.name || plant.id}{plant.city ? ` · ${plant.city}` : ""}</option>)}
          </select>
          <label htmlFor="owner-name">Owner name</label><input id="owner-name" value={name} onChange={(event) => setName(event.target.value)} required />
          <label htmlFor="owner-email">Approved Owner email</label><input id="owner-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <label htmlFor="owner-phone">Owner mobile (optional)</label><input id="owner-phone" value={phone} onChange={(event) => setPhone(event.target.value)} />
          {error && <div className="errorBanner" role="alert">{error}</div>}
          <button className="primaryButton" type="submit" disabled={Boolean(busy) || plants.length === 0}>{busy === "assign-owner" ? "Assigning…" : "Approve Owner access"}</button>
        </form>
        <Notice>Owner approval creates/reuses only a Plant Owner account, links it to the selected plant, and preserves the existing Plant Staff email OTP/MFA login flow.</Notice>
      </div>
    </section>
  </div>;
}

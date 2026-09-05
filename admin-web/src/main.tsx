import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { type AdminUser, get, type Home, post } from "./api";
import { DataWorkspace, type PortalModule } from "./workspaces";
import "./styles.css";

type Session = { access_token: string };
type ModuleKey = "Dashboard" | "Security" | PortalModule;
type ModuleDefinition = {
  key: ModuleKey;
  label: string;
  short: string;
  group: "Operations" | "Governance";
  description: string;
};

const modules: ModuleDefinition[] = [
  { key: "Dashboard", label: "Command Center", short: "DC", group: "Operations", description: "Platform-wide operational visibility and privileged oversight." },
  { key: "Plants", label: "Plants", short: "PL", group: "Operations", description: "Review plant records and authority-controlled operational data." },
  { key: "Users", label: "Users", short: "US", group: "Operations", description: "Review customer, staff and partner identities under server-side RBAC." },
  { key: "KYC", label: "KYC", short: "KY", group: "Operations", description: "Review verification status without bypassing DigiLocker or approval rules." },
  { key: "Orders", label: "Orders", short: "OR", group: "Operations", description: "Inspect order lifecycle information and operational exceptions." },
  { key: "Payments", label: "Payments", short: "PY", group: "Operations", description: "Review payment status and reconciliation surfaces governed by backend contracts." },
  { key: "Support", label: "Support", short: "SP", group: "Operations", description: "Central support and escalation workspace for approved administrators." },
  { key: "Security", label: "Security", short: "SC", group: "Governance", description: "Manage your privileged session posture and fresh identity verification." },
  { key: "Audit Logs", label: "Audit Logs", short: "AL", group: "Governance", description: "Audit-oriented workspace for privileged administrative activity." },
  { key: "System", label: "System", short: "SY", group: "Governance", description: "System status and controlled platform administration." },
];

const CENTRAL_ADMIN_ONLY = new Set<ModuleKey>(["Users", "Audit Logs", "System"]);

function Brand({ label, compact = false }: { label: string; compact?: boolean }) {
  return (
    <div className={`brand${compact ? " brandCompact" : ""}`}>
      <span className="brandMark" aria-hidden="true">CK</span>
      <div>
        <b>TrackMyRMC</b>
        <small>{label}</small>
      </div>
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 19 6v5c0 4.8-2.8 8.2-7 10-4.2-1.8-7-5.2-7-10V6l7-3Z" />
      <path d="m9.2 12 1.8 1.8 3.9-4" />
    </svg>
  );
}

function Login({ onLogin }: { onLogin(token: string, user: AdminUser): void }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await post<Session>("/admin/auth/verify-totp", { identifier: email.trim(), code });
      const user = await get<AdminUser>("/me", session.access_token);
      onLogin(session.access_token, user);
    } catch {
      setError("Authentication failed. Check your approved administrator account and Authenticator code.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="loginPage">
      <section className="loginStory" aria-label="TrackMyRMC secure administration">
        <Brand label="Privileged Administration" />
        <div className="loginStoryCopy">
          <p className="eyebrow">ADMIN.TRACKMYRMC.COM</p>
          <h1>Control the platform from a dedicated secure surface.</h1>
          <p className="lead">Central administration is intentionally separated from the public mobile application. Security boundaries stay visible at every privileged step.</p>
        </div>
        <div className="securityPillars">
          <article><span><ShieldIcon /></span><div><b>MFA required</b><small>Authenticator verification on privileged sign-in.</small></div></article>
          <article><span>05</span><div><b>Five-minute step-up</b><small>Fresh verification is required before high-risk operations.</small></div></article>
          <article><span>0×</span><div><b>No browser storage</b><small>Bearer sessions remain in protected runtime memory.</small></div></article>
        </div>
        <div className="loginArt" aria-hidden="true"><i /><i /><i /><span>SECURE CONTROL PLANE</span></div>
      </section>

      <section className="loginPanel">
        <div className="loginCard">
          <div className="mobileBrand"><Brand label="Secure Administration" /></div>
          <div className="secureBadge"><ShieldIcon /><span>Restricted administrator portal</span></div>
          <p className="eyebrow">PRIVILEGED ACCESS</p>
          <h2>Welcome back</h2>
          <p>Use an approved Authority or Central Admin account. Account registration is not available on this portal.</p>
          <form onSubmit={submit} noValidate>
            <label htmlFor="admin-email">Administrator email</label>
            <input id="admin-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@company.com" required />
            <label htmlFor="admin-code">Authenticator code</label>
            <div className="codeInputWrap">
              <input id="admin-code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,8}" minLength={6} maxLength={8} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} placeholder="000000" required />
              <span aria-hidden="true">MFA</span>
            </div>
            {error && <div className="errorBanner" role="alert">{error}</div>}
            <button className="primaryButton" type="submit" disabled={busy || code.length < 6}>{busy ? "Verifying securely…" : "Verify and continue"}</button>
          </form>
          <div className="runtimeNote"><ShieldIcon /><span>Your session is kept in memory only and is cleared when you sign out or close the portal.</span></div>
        </div>
        <p className="portalFootnote">TrackMyRMC • Privileged access is monitored and audit oriented.</p>
      </section>
    </main>
  );
}

function KpiCard({ label, value, loading }: { label: string; value?: number; loading?: boolean }) {
  return (
    <article className="kpiCard">
      <div className="kpiTop"><small>{label}</small><span aria-hidden="true">↗</span></div>
      {loading ? <div className="skeleton skeletonValue" /> : <strong>{new Intl.NumberFormat("en-IN").format(value ?? 0)}</strong>}
      <span className="kpiHint">Live administrative summary</span>
    </article>
  );
}

function Panel({ title, eyebrow, children, action }: { title: string; eyebrow?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="panel">
      <header className="panelHeader">
        <div>{eyebrow && <small>{eyebrow}</small>}<h3>{title}</h3></div>
        {action}
      </header>
      <div className="panelBody">{children}</div>
    </section>
  );
}

function StepUpDialog({ onClose, onVerified, token }: { onClose(): void; onVerified(): void; token: string }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post("/admin/auth/step-up", { code }, token);
      onVerified();
      onClose();
    } catch {
      setError("Identity confirmation failed. Enter a fresh Authenticator code and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="dialogBackdrop" role="presentation">
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="stepup-title">
        <div className="dialogIcon"><ShieldIcon /></div>
        <p className="eyebrow">SECURITY STEP-UP</p>
        <h3 id="stepup-title">Confirm your identity</h3>
        <p>Enter a fresh Authenticator code. Successful confirmation is recognized for five minutes by the protected admin flow.</p>
        <form onSubmit={submit}>
          <label htmlFor="stepup-code">Authenticator code</label>
          <input id="stepup-code" autoFocus inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,8}" minLength={6} maxLength={8} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} placeholder="000000" required />
          {error && <div className="errorBanner" role="alert">{error}</div>}
          <div className="dialogActions"><button className="secondaryButton" type="button" onClick={onClose} disabled={busy}>Cancel</button><button className="primaryButton" type="submit" disabled={busy || code.length < 6}>{busy ? "Verifying…" : "Verify identity"}</button></div>
        </form>
      </section>
    </div>
  );
}

function ConfirmDialog({ onCancel, onConfirm, busy }: { onCancel(): void; onConfirm(): void; busy: boolean }) {
  return (
    <div className="dialogBackdrop" role="presentation">
      <section className="dialog dangerDialog" role="alertdialog" aria-modal="true" aria-labelledby="revoke-title">
        <div className="dialogIcon dangerIcon" aria-hidden="true">!</div>
        <p className="eyebrow dangerText">DESTRUCTIVE SESSION ACTION</p>
        <h3 id="revoke-title">Revoke all your administrator sessions?</h3>
        <p>This signs your administrator account out everywhere. You will need MFA again to return to this portal.</p>
        <div className="dialogActions"><button className="secondaryButton" type="button" onClick={onCancel} disabled={busy}>Keep sessions</button><button className="dangerButton" type="button" onClick={onConfirm} disabled={busy}>{busy ? "Revoking…" : "Revoke all sessions"}</button></div>
      </section>
    </div>
  );
}

function Dashboard({ home, user, stepUpFresh, requestStepUp }: { home?: Home; user: AdminUser; stepUpFresh: boolean; requestStepUp(): void }) {
  const kpis = home?.kpis ?? [];
  return (
    <>
      <section className="heroPanel">
        <div>
          <p className="eyebrow">PRIVILEGED COMMAND CENTER</p>
          <h2>Good to see you, {user.name.split(" ")[0] || "Administrator"}.</h2>
          <p>Platform-level visibility lives here; customer and plant operations remain in their role-specific application surfaces.</p>
        </div>
        <div className="heroSecurity"><span className={stepUpFresh ? "statusDot fresh" : "statusDot"} /><div><b>{stepUpFresh ? "Identity freshly verified" : "Standard privileged session"}</b><small>{stepUpFresh ? "Five-minute step-up window is active." : "High-risk actions will request fresh MFA."}</small></div></div>
      </section>

      <div className="kpiGrid">
        {kpis.length ? kpis.slice(0, 4).map((kpi) => <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />) : ["Plants", "Users", "Active Orders", "Open Support"].map((label) => <KpiCard key={label} label={label} loading />)}
      </div>

      <div className="dashboardGrid">
        <Panel title="Administration overview" eyebrow="CONTROL PLANE" action={<button className="textButton" type="button" onClick={requestStepUp}>Confirm identity</button>}>
          <div className="overviewList">
            <article><span className="overviewNumber">01</span><div><b>Mobile boundary protected</b><p>Central Admin and Authority remain outside the public mobile route tree.</p></div></article>
            <article><span className="overviewNumber">02</span><div><b>Backend remains authoritative</b><p>Portal records are read from server-authorized, data-minimized admin APIs.</p></div></article>
            <article><span className="overviewNumber">03</span><div><b>High-risk actions need step-up</b><p>This release keeps operational workspaces read-only; destructive admin actions stay behind dedicated audited flows.</p></div></article>
          </div>
        </Panel>
        <Panel title="Security posture" eyebrow="CURRENT SESSION">
          <div className="securityScore"><div className="scoreRing"><span>3</span><small>/ 3</small></div><div><b>Core controls active</b><p>MFA sign-in, memory-only bearer session and server-side role verification are part of this admin surface.</p></div></div>
          <div className="statusRows"><span><i className="okDot" />Authenticator MFA</span><span><i className="okDot" />Memory-only session</span><span><i className="okDot" />Privileged web separation</span></div>
        </Panel>
      </div>
    </>
  );
}

function ModuleWorkspace({ module, token, requestStepUp, onLogout }: { module: ModuleDefinition; token: string; requestStepUp(): void; onLogout(): void }) {
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [revoking, setRevoking] = useState(false);

  async function revokeAll() {
    setRevoking(true);
    await post("/admin/auth/logout-all", {}, token).catch(() => undefined);
    setRevoking(false);
    setConfirmRevoke(false);
    onLogout();
  }

  if (module.key === "Security") {
    return (
      <div className="moduleGrid">
        <Panel title="Identity protection" eyebrow="SECURITY">
          <div className="settingsList">
            <article><div><b>Fresh identity confirmation</b><p>Re-verify with Authenticator before high-risk administrative operations.</p></div><button className="secondaryButton" type="button" onClick={requestStepUp}>Confirm identity</button></article>
            <article><div><b>Session storage</b><p>The bearer token remains in React runtime memory and is never intentionally persisted to local or session storage.</p></div><span className="stateBadge">Memory only</span></article>
          </div>
        </Panel>
        <Panel title="Session revocation" eyebrow="HIGH-RISK ACTION">
          <div className="dangerZone"><div className="dangerIcon" aria-hidden="true">!</div><h4>Sign out everywhere</h4><p>Immediately revoke all active administrator sessions associated with your account.</p><button className="dangerButton" type="button" onClick={() => setConfirmRevoke(true)}>Revoke all sessions</button></div>
        </Panel>
        {confirmRevoke && <ConfirmDialog busy={revoking} onCancel={() => setConfirmRevoke(false)} onConfirm={revokeAll} />}
      </div>
    );
  }

  if (module.key !== "Dashboard") return <DataWorkspace module={module.key} token={token} />;
  return null;
}

function Portal({ token, user, onLogout }: { token: string; user: AdminUser; onLogout(): void }) {
  const [active, setActive] = useState<ModuleKey>("Dashboard");
  const [home, setHome] = useState<Home>();
  const [dark, setDark] = useState(true);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [stepUpUntil, setStepUpUntil] = useState<number | null>(null);

  const visibleModules = useMemo(() => modules.filter((item) => user.role === "central_admin" || !CENTRAL_ADMIN_ONLY.has(item.key)), [user.role]);
  const currentModule = useMemo(() => visibleModules.find((item) => item.key === active) ?? visibleModules[0], [active, visibleModules]);
  const stepUpFresh = Boolean(stepUpUntil && stepUpUntil > Date.now());

  useEffect(() => {
    let mounted = true;
    get<Home>("/admin/portal/summary", token).then((value) => { if (mounted) setHome(value); }).catch(() => { if (mounted) onLogout(); });
    return () => { mounted = false; };
  }, [token, onLogout]);

  useEffect(() => {
    if (!visibleModules.some((item) => item.key === active)) setActive("Dashboard");
  }, [active, visibleModules]);

  useEffect(() => {
    if (!stepUpUntil) return;
    const timer = window.setTimeout(() => setStepUpUntil(null), Math.max(0, stepUpUntil - Date.now()));
    return () => window.clearTimeout(timer);
  }, [stepUpUntil]);

  return (
    <div className={`shell${dark ? " dark" : ""}`}>
      <aside className="sidebar">
        <Brand label="Administration" />
        <div className="portalTag"><ShieldIcon /><span>Privileged web only</span></div>
        {(["Operations", "Governance"] as const).map((group) => (
          <section className="navGroup" key={group} aria-label={group}>
            <small>{group}</small>
            {visibleModules.filter((item) => item.group === group).map((item) => (
              <button key={item.key} className={active === item.key ? "navItem active" : "navItem"} type="button" aria-current={active === item.key ? "page" : undefined} onClick={() => setActive(item.key)}>
                <span aria-hidden="true">{item.short}</span><b>{item.label}</b>
              </button>
            ))}
          </section>
        ))}
        <div className="sidebarFoot"><span className="statusDot fresh" /><div><b>Secure connection</b><small>Role-gated portal</small></div></div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p className="eyebrow">SECURE PORTAL</p><h1>{currentModule.label}</h1></div>
          <div className="account">
            <button className="iconButton" type="button" onClick={() => setDark((value) => !value)} aria-label={`Switch to ${dark ? "light" : "dark"} theme`}>{dark ? "☀" : "◐"}</button>
            <div className="accountIdentity"><span className="avatar" aria-hidden="true">{user.name.slice(0, 1).toUpperCase()}</span><div><b>{user.name}</b><small>{user.role_label}</small></div></div>
            <button className="secondaryButton compactButton" type="button" onClick={onLogout}>Logout</button>
          </div>
        </header>

        <main className="content">
          <div className="securityNotice"><div className="noticeIcon"><ShieldIcon /></div><div><b>MFA-protected administration</b><span>Operational workspaces are read-only; high-risk mutations remain in dedicated server-audited flows with fresh verification where required.</span></div><button className={stepUpFresh ? "verifiedButton" : "secondaryButton"} type="button" onClick={() => setStepUpOpen(true)}>{stepUpFresh ? "Identity verified" : "Confirm identity"}</button></div>
          {active === "Dashboard" ? <Dashboard home={home} user={user} stepUpFresh={stepUpFresh} requestStepUp={() => setStepUpOpen(true)} /> : <ModuleWorkspace module={currentModule} token={token} requestStepUp={() => setStepUpOpen(true)} onLogout={onLogout} />}
        </main>
      </section>

      {stepUpOpen && <StepUpDialog token={token} onClose={() => setStepUpOpen(false)} onVerified={() => setStepUpUntil(Date.now() + 5 * 60 * 1000)} />}
    </div>
  );
}

function App() {
  const [session, setSession] = useState<{ token: string; user: AdminUser } | null>(null);
  return session ? <Portal token={session.token} user={session.user} onLogout={() => setSession(null)} /> : <Login onLogin={(token, user) => setSession({ token, user })} />;
}

createRoot(document.getElementById("root")!).render(<App />);

import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { type AdminUser, get, type Home, post } from "./api";
import { CommandCenter } from "./command-center";
import { AICommandCenter } from "./ai-command-center";
import { DataWorkspace, type PortalModule } from "./workspaces";
import "./styles.css";

type Session = { access_token: string };
type ModuleKey = string;
type ModuleDefinition = {
  key: ModuleKey;
  label: string;
  short: string;
  group: "Command" | "Support" | "Plants" | "Growth" | "AI & Automation" | "System" | "Security";
  description: string;
};

const catalog: Record<ModuleDefinition["group"], string[]> = {
  Command: ["Dashboard", "AI Command Center", "Incidents", "Approval Queue"],
  Support: ["Users", "Login / OTP", "KYC", "GPS Tracking", "Payments", "Problem Resolver"],
  Plants: ["All Plants", "Plant 360", "Onboarding", "Verification", "Owners / Staff", "Fleet", "Data Quality"],
  Growth: ["Marketing AI", "Campaigns", "WhatsApp", "Proposals", "Leads CRM", "Invitations", "Banner Studio", "Promotions", "Premium Plans"],
  "AI & Automation": ["AI Providers", "Model Routing", "Automations", "AI Usage / Cost", "AI Audit"],
  System: ["API Health", "OTP Health", "KYC Health", "GPS Health", "Payment Health", "Webhooks", "Errors", "Integrations", "Releases"],
  Security: ["Admins", "Roles", "Permissions", "Sessions", "Devices", "Security Alerts", "Audit Logs"],
};
const modules: ModuleDefinition[] = Object.entries(catalog).flatMap(([group, labels]) => labels.map((label) => ({ key: label, label, short: label.split(/\s|\//).filter(Boolean).map((word) => word[0]).join("").slice(0, 2).toUpperCase(), group: group as ModuleDefinition["group"], description: `${label} is protected by Control Center authorization and immutable audit policy.` })));
const DATA_MODULES = new Set(["Users", "KYC", "Payments", "Audit Logs"]);

function Brand({ label, compact = false }: { label: string; compact?: boolean }) {
  return (
    <div className={`brand${compact ? " brandCompact" : ""}`}>
      <span className="brandMark" aria-hidden="true">CK</span>
      <div><b>TrackMyRMC</b><small>{label}</small></div>
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
          <p className="eyebrow">CONTROL.TRACKMYRMC.COM</p>
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
          <p>Use an explicitly approved Super Admin account with MFA. Authority and mobile accounts are always denied.</p>
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

function ModuleWorkspace({ module, token, stepUpFresh, requestStepUp, onLogout }: { module: ModuleDefinition; token: string; stepUpFresh: boolean; requestStepUp(): void; onLogout(): void }) {
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

  if (module.key === "AI Command Center") return <AICommandCenter token={token} mfaVerified={stepUpFresh} requestStepUp={requestStepUp} />;

  if (DATA_MODULES.has(module.key)) return <DataWorkspace module={module.key as PortalModule} token={token} />;
  if (module.key === "All Plants") return <DataWorkspace module="Plants" token={token} />;
  if (module.key !== "Dashboard") return <section className="portalWorkspaceCard"><div className="emptyWorkspace"><span className="emptyGlyph">{module.short}</span><h4>{module.label}</h4><p>{module.description}</p><small>Safe actions become available only when their backend permission, validation, approval, and audit contracts are configured.</small></div></section>;
  return null;
}

function Portal({ token, user, onLogout }: { token: string; user: AdminUser; onLogout(): void }) {
  const [active, setActive] = useState<ModuleKey>("Dashboard");
  const [home, setHome] = useState<Home>();
  const [dark, setDark] = useState(true);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [stepUpUntil, setStepUpUntil] = useState<number | null>(null);

  const visibleModules = modules;
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
        {(Object.keys(catalog) as ModuleDefinition["group"][]).map((group) => (
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
          {active === "Dashboard" ? <CommandCenter home={home} user={user} stepUpFresh={stepUpFresh} requestStepUp={() => setStepUpOpen(true)} /> : <ModuleWorkspace module={currentModule} token={token} stepUpFresh={stepUpFresh} requestStepUp={() => setStepUpOpen(true)} onLogout={onLogout} />}
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

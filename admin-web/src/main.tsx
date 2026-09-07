import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { type AdminUser, get, type Home, post } from "./api";
import { CommandCenter } from "./command-center";
import { AICommandCenter } from "./ai-command-center";
import { AdminAccessWorkspace, OwnerAccessWorkspace, ReviewerAccessWorkspace } from "./access-control-center";
import { PermissionsWorkspace, RolesWorkspace, SessionsWorkspace, SupportWorkspace } from "./security-workspaces";
import { DataWorkspace } from "./workspaces";
import "./styles.css";

type Session = { access_token: string };
type Group = "Command" | "Support" | "Plants" | "Growth" | "AI & Automation" | "System" | "Security";
type ModuleStatus = "active" | "read_only" | "planned";
type WorkspaceKey = "dashboard" | "ai" | "users" | "kyc" | "payments" | "plants" | "orders" | "support" | "system" | "owners" | "reviewer" | "admins" | "permissions" | "sessions" | "roles" | "security" | "audit" | "planned";
type ModuleDefinition = {
  key: string; label: string; group: Group; workspace: WorkspaceKey; requiredPermission: string | null;
  status: ModuleStatus; badge?: string; description: string;
};
type Capabilities = { permissions: string[]; allowed_module_keys: string[]; session_security: { auth_surface: string; control_center_mfa: boolean; recent_mfa_step_up: boolean }; constraints: string[] };

const modules: ModuleDefinition[] = [
  { key: "Dashboard", label: "Dashboard", group: "Command", workspace: "dashboard", requiredPermission: null, status: "active", description: "Permission-aware platform summary." },
  { key: "AI Command Center", label: "AI Command Center", group: "Command", workspace: "ai", requiredPermission: "ai.diagnose", status: "active", description: "Policy-gated diagnostic and draft workflow surface." },
  { key: "Incidents", label: "Incidents", group: "Command", workspace: "planned", requiredPermission: "incident.resolve", status: "planned", badge: "PLANNED", description: "No complete Control Center backend contract exists yet." },
  { key: "Approval Queue", label: "Approval Queue", group: "Command", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "Unified approval queue is not yet backed by a safe contract." },

  { key: "Users", label: "Users", group: "Support", workspace: "users", requiredPermission: "user.view", status: "read_only", badge: "READ ONLY", description: "Safe user metadata." },
  { key: "Orders", label: "Orders", group: "Support", workspace: "orders", requiredPermission: "order.view", status: "read_only", badge: "READ ONLY", description: "Safe order lifecycle metadata." },
  { key: "Support", label: "Support", group: "Support", workspace: "support", requiredPermission: "support.view", status: "active", description: "Audited support case management." },
  { key: "Login / OTP", label: "Login / OTP", group: "Support", workspace: "planned", requiredPermission: "login.unlock", status: "planned", badge: "PLANNED", description: "No standalone safe OTP administration contract is exposed." },
  { key: "KYC", label: "KYC", group: "Support", workspace: "kyc", requiredPermission: "kyc.view", status: "read_only", badge: "READ ONLY", description: "Verification-state metadata only." },
  { key: "GPS Tracking", label: "GPS Tracking", group: "Support", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "No Control Center GPS contract exists yet." },
  { key: "Payments", label: "Payments", group: "Support", workspace: "payments", requiredPermission: "payment.view", status: "read_only", badge: "READ ONLY", description: "Read-only payment state." },
  { key: "Problem Resolver", label: "Problem Resolver", group: "Support", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "Automated remediation is not exposed." },

  { key: "All Plants", label: "All Plants", group: "Plants", workspace: "plants", requiredPermission: "plant.view", status: "read_only", badge: "READ ONLY", description: "Safe plant directory metadata." },
  { key: "Plant 360", label: "Plant 360", group: "Plants", workspace: "planned", requiredPermission: "plant.view", status: "planned", badge: "PLANNED", description: "Plant 360 has no complete backend contract." },
  { key: "Onboarding", label: "Onboarding", group: "Plants", workspace: "owners", requiredPermission: "owner.view", status: "active", description: "Pending Owner onboarding through Control Center routes." },
  { key: "Verification", label: "Verification", group: "Plants", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "No separate verification workspace contract." },
  { key: "Owners / Staff", label: "Owners / Staff", group: "Plants", workspace: "owners", requiredPermission: "owner.view", status: "active", description: "Owner approval and assignment with fresh MFA." },
  { key: "Fleet", label: "Fleet", group: "Plants", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "Fleet administration is not wired to Control Center." },
  { key: "Data Quality", label: "Data Quality", group: "Plants", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "Data quality remediation is not yet operational." },

  ...["Marketing AI", "Campaigns", "WhatsApp", "Proposals", "Leads CRM", "Invitations", "Banner Studio", "Promotions", "Premium Plans"].map((label): ModuleDefinition => ({ key: label, label, group: "Growth", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "No safe Control Center backend contract exists for this module yet." })),
  ...["AI Providers", "Model Routing", "Automations", "AI Usage / Cost", "AI Audit"].map((label): ModuleDefinition => ({ key: label, label, group: "AI & Automation", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "This advanced AI/automation module is intentionally not presented as live." })),

  { key: "System", label: "System", group: "System", workspace: "system", requiredPermission: "system.view", status: "read_only", badge: "READ ONLY", description: "Safe system health metadata." },
  ...["API Health", "OTP Health", "KYC Health", "GPS Health", "Payment Health", "Webhooks", "Errors", "Integrations", "Releases"].map((label): ModuleDefinition => ({ key: label, label, group: "System", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "No dedicated live Control Center contract exists for this module." })),

  { key: "Security Overview", label: "Security Overview", group: "Security", workspace: "security", requiredPermission: "session.view", status: "active", description: "Session posture and self-revocation controls." },
  { key: "Reviewer Access", label: "Reviewer Access", group: "Security", workspace: "reviewer", requiredPermission: "reviewer_access.manage", status: "active", description: "Runtime Play reviewer access control." },
  { key: "Admins", label: "Admins", group: "Security", workspace: "admins", requiredPermission: "admin_access.manage", status: "active", description: "Central Admin approval and suspension." },
  { key: "Roles", label: "Roles", group: "Security", workspace: "roles", requiredPermission: "permissions.manage", status: "read_only", badge: "READ ONLY", description: "Authentication-boundary role templates." },
  { key: "Permissions", label: "Permissions", group: "Security", workspace: "permissions", requiredPermission: "permissions.manage", status: "active", description: "Explicit permission grants with fresh MFA and audit reason." },
  { key: "Sessions", label: "Sessions", group: "Security", workspace: "sessions", requiredPermission: "session.view", status: "active", description: "Safe administrator session metadata and revocation." },
  { key: "Devices", label: "Devices", group: "Security", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "Device inventory is not backed by reliable data yet." },
  { key: "Security Alerts", label: "Security Alerts", group: "Security", workspace: "planned", requiredPermission: null, status: "planned", badge: "PLANNED", description: "Security alert feed is not backed by a live contract yet." },
  { key: "Audit Logs", label: "Audit Logs", group: "Security", workspace: "audit", requiredPermission: "audit.view", status: "read_only", badge: "READ ONLY", description: "Safe audit metadata." },
];

function initials(label: string) { return label.split(/\s|\//).filter(Boolean).map((word) => word[0]).join("").slice(0, 2).toUpperCase(); }

function Brand({ label, compact = false }: { label: string; compact?: boolean }) {
  return <div className={`brand${compact ? " brandCompact" : ""}`}><span className="brandMark" aria-hidden="true">CK</span><div><b>TrackMyRMC</b><small>{label}</small></div></div>;
}
function ShieldIcon() { return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 19 6v5c0 4.8-2.8 8.2-7 10-4.2-1.8-7-5.2-7-10V6l7-3Z" /><path d="m9.2 12 1.8 1.8 3.9-4" /></svg>; }

function Login({ onLogin }: { onLogin(token: string, user: AdminUser): void }) {
  const [email, setEmail] = useState(""); const [code, setCode] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { const session = await post<Session>("/admin/auth/verify-totp", { identifier: email.trim(), code }); const user = await get<AdminUser>("/me", session.access_token); onLogin(session.access_token, user); } catch { setError("Authentication failed. Use an approved Central Admin identity with enrolled Authenticator MFA."); } finally { setBusy(false); } }
  return <main className="loginPage"><section className="loginStory" aria-label="TrackMyRMC secure administration"><Brand label="Privileged Administration" /><div className="loginStoryCopy"><p className="eyebrow">CONTROL.TRACKMYRMC.COM</p><h1>Control the platform from a dedicated secure surface.</h1><p className="lead">Central Admin is web-Control-Center only after MFA enrollment. Authority remains an operational Plant Staff email/MFA role and does not sign in here.</p></div><div className="securityPillars"><article><span><ShieldIcon /></span><div><b>MFA required</b><small>Authenticator verification on privileged sign-in.</small></div></article><article><span>05</span><div><b>Five-minute step-up</b><small>Fresh verification before high-risk operations.</small></div></article><article><span>0×</span><div><b>No browser storage</b><small>Bearer sessions remain in runtime memory.</small></div></article></div></section><section className="loginPanel"><div className="loginCard"><div className="mobileBrand"><Brand label="Secure Administration" /></div><div className="secureBadge"><ShieldIcon /><span>Central Admin Control Center</span></div><p className="eyebrow">PRIVILEGED WEB ACCESS</p><h2>Sign in</h2><p>Plant Owner, Authority and Plant Staff continue through the approved Plant Staff email/MFA flow. This portal accepts Central Admin only.</p><form onSubmit={submit}><label htmlFor="admin-email">Central Admin email</label><input id="admin-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /><label htmlFor="admin-code">Authenticator code</label><input id="admin-code" inputMode="numeric" autoComplete="one-time-code" minLength={6} maxLength={8} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} placeholder="000000" required />{error && <div className="errorBanner" role="alert">{error}</div>}<button className="primaryButton" disabled={busy || code.length < 6}>{busy ? "Verifying…" : "Verify and continue"}</button></form><div className="runtimeNote"><ShieldIcon /><span>First-time MFA bootstrap and recovery never become privileged sessions. After enrollment, sign in again here.</span></div></div></section></main>;
}

function Panel({ title, eyebrow, children }: { title: string; eyebrow?: string; children: ReactNode }) { return <section className="panel"><header className="panelHeader"><div>{eyebrow && <small>{eyebrow}</small>}<h3>{title}</h3></div></header><div className="panelBody">{children}</div></section>; }

function StepUpDialog({ onClose, onVerified, token }: { onClose(): void; onVerified(): void; token: string }) {
  const [code, setCode] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { await post("/admin/auth/step-up", { code }, token); onVerified(); onClose(); } catch { setError("Identity confirmation failed. Enter a fresh Authenticator code."); } finally { setBusy(false); } }
  return <div className="dialogBackdrop"><section className="dialog" role="dialog" aria-modal="true"><div className="dialogIcon"><ShieldIcon /></div><p className="eyebrow">SECURITY STEP-UP</p><h3>Confirm your identity</h3><form onSubmit={submit}><label htmlFor="stepup-code">Authenticator code</label><input id="stepup-code" autoFocus inputMode="numeric" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} minLength={6} maxLength={8} required />{error && <div className="errorBanner" role="alert">{error}</div>}<div className="dialogActions"><button className="secondaryButton" type="button" onClick={onClose}>Cancel</button><button className="primaryButton" disabled={busy || code.length < 6}>Verify identity</button></div></form></section></div>;
}

function SecurityOverview({ token, requestStepUp, stepUpFresh, onLogout }: { token: string; requestStepUp(): void; stepUpFresh: boolean; onLogout(): void }) {
  const [busy, setBusy] = useState(false);
  async function revokeAll() { if (!stepUpFresh) { requestStepUp(); return; } setBusy(true); await post("/admin/auth/logout-all", {}, token).catch(() => undefined); setBusy(false); onLogout(); }
  return <div className="moduleGrid"><Panel title="Identity protection" eyebrow="SECURITY"><div className="settingsList"><article><div><b>Control Center provenance</b><p>Central Admin APIs require server-marked <code>control_center_web</code> MFA provenance.</p></div><span className="stateBadge">Required</span></article><article><div><b>Fresh identity confirmation</b><p>High-risk actions require a five-minute step-up window.</p></div><button className="secondaryButton" onClick={requestStepUp}>{stepUpFresh ? "Verified" : "Confirm identity"}</button></article></div></Panel><Panel title="Session revocation" eyebrow="HIGH-RISK ACTION"><p>Revoke every active session for your administrator identity.</p><button className="dangerButton" disabled={busy} onClick={() => void revokeAll()}>{busy ? "Revoking…" : "Revoke all sessions"}</button></Panel></div>;
}

function PlannedWorkspace({ module }: { module: ModuleDefinition }) { return <section className="portalWorkspaceCard"><div className="emptyWorkspace"><span className="emptyGlyph">{initials(module.label)}</span><h4>{module.label} · PLANNED</h4><p>{module.description}</p><small>No fabricated live values or destructive controls are exposed.</small></div></section>; }

function ModuleWorkspace({ module, token, stepUpFresh, requestStepUp, onLogout }: { module: ModuleDefinition; token: string; stepUpFresh: boolean; requestStepUp(): void; onLogout(): void }) {
  switch (module.workspace) {
    case "ai": return <AICommandCenter token={token} mfaVerified={stepUpFresh} requestStepUp={requestStepUp} />;
    case "reviewer": return <ReviewerAccessWorkspace token={token} stepUpFresh={stepUpFresh} requestStepUp={requestStepUp} />;
    case "admins": return <AdminAccessWorkspace token={token} stepUpFresh={stepUpFresh} requestStepUp={requestStepUp} />;
    case "owners": return <OwnerAccessWorkspace token={token} stepUpFresh={stepUpFresh} requestStepUp={requestStepUp} />;
    case "permissions": return <PermissionsWorkspace token={token} stepUpFresh={stepUpFresh} requestStepUp={requestStepUp} />;
    case "sessions": return <SessionsWorkspace token={token} stepUpFresh={stepUpFresh} requestStepUp={requestStepUp} onCurrentRevoked={onLogout} />;
    case "support": return <SupportWorkspace token={token} stepUpFresh={stepUpFresh} requestStepUp={requestStepUp} />;
    case "roles": return <RolesWorkspace />;
    case "security": return <SecurityOverview token={token} stepUpFresh={stepUpFresh} requestStepUp={requestStepUp} onLogout={onLogout} />;
    case "users": return <DataWorkspace module="Users" token={token} />;
    case "kyc": return <DataWorkspace module="KYC" token={token} />;
    case "payments": return <DataWorkspace module="Payments" token={token} />;
    case "plants": return <DataWorkspace module="Plants" token={token} />;
    case "orders": return <DataWorkspace module="Orders" token={token} />;
    case "audit": return <DataWorkspace module="Audit Logs" token={token} />;
    case "system": return <DataWorkspace module="System" token={token} />;
    case "planned": return <PlannedWorkspace module={module} />;
    default: return null;
  }
}

function Portal({ token, user, onLogout }: { token: string; user: AdminUser; onLogout(): void }) {
  const [active, setActive] = useState("Dashboard"); const [home, setHome] = useState<Home>(); const [capabilities, setCapabilities] = useState<Capabilities>(); const [dark, setDark] = useState(true); const [stepUpOpen, setStepUpOpen] = useState(false); const [stepUpUntil, setStepUpUntil] = useState<number | null>(null);
  const stepUpFresh = Boolean(stepUpUntil && stepUpUntil > Date.now());
  useEffect(() => { let mounted = true; Promise.all([get<Home>("/admin/portal/summary", token), get<Capabilities>("/control-center/capabilities", token)]).then(([summary, caps]) => { if (mounted) { setHome(summary); setCapabilities(caps); } }).catch(() => { if (mounted) onLogout(); }); return () => { mounted = false; }; }, [token, onLogout]);
  const visibleModules = useMemo(() => modules.filter((module) => module.status === "planned" || module.requiredPermission === null || capabilities?.permissions.includes(module.requiredPermission)), [capabilities]);
  const currentModule = useMemo(() => visibleModules.find((item) => item.key === active) ?? modules[0], [active, visibleModules]);
  useEffect(() => { if (!visibleModules.some((item) => item.key === active)) setActive("Dashboard"); }, [active, visibleModules]);
  useEffect(() => { if (!stepUpUntil) return; const timer = window.setTimeout(() => setStepUpUntil(null), Math.max(0, stepUpUntil - Date.now())); return () => window.clearTimeout(timer); }, [stepUpUntil]);

  return <div className={`shell${dark ? " dark" : ""}`}><aside className="sidebar"><Brand label="Administration" /><div className="portalTag"><ShieldIcon /><span>Privileged web only</span></div>{(["Command", "Support", "Plants", "Growth", "AI & Automation", "System", "Security"] as Group[]).map((group) => <section className="navGroup" key={group}><small>{group}</small>{visibleModules.filter((item) => item.group === group).map((item) => <button key={item.key} className={active === item.key ? "navItem active" : "navItem"} type="button" disabled={item.status === "planned"} onClick={() => item.status !== "planned" && setActive(item.key)}><span aria-hidden="true">{initials(item.label)}</span><b>{item.label}</b>{item.badge ? <small>{item.badge}</small> : null}</button>)}</section>)}</aside><section className="workspace"><header className="topbar"><div><p className="eyebrow">SECURE CONTROL CENTER</p><h1>{currentModule.label}</h1></div><div className="account"><button className="iconButton" onClick={() => setDark((value) => !value)}>{dark ? "☀" : "◐"}</button><div className="accountIdentity"><span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span><div><b>{user.name}</b><small>{user.role_label}</small></div></div><button className="secondaryButton compactButton" onClick={onLogout}>Logout</button></div></header><main className="content"><div className="securityNotice"><div className="noticeIcon"><ShieldIcon /></div><div><b>Least-privilege Control Center</b><span>{capabilities ? `${capabilities.permissions.length} effective permission(s) · ${capabilities.session_security.auth_surface}` : "Loading effective permissions…"}</span></div><button className={stepUpFresh ? "verifiedButton" : "secondaryButton"} onClick={() => setStepUpOpen(true)}>{stepUpFresh ? "Identity verified" : "Confirm identity"}</button></div>{active === "Dashboard" ? <CommandCenter home={home} user={user} stepUpFresh={stepUpFresh} requestStepUp={() => setStepUpOpen(true)} /> : <ModuleWorkspace module={currentModule} token={token} stepUpFresh={stepUpFresh} requestStepUp={() => setStepUpOpen(true)} onLogout={onLogout} />}</main></section>{stepUpOpen && <StepUpDialog token={token} onClose={() => setStepUpOpen(false)} onVerified={() => setStepUpUntil(Date.now() + 5 * 60 * 1000)} />}</div>;
}

function App() { const [session, setSession] = useState<{ token: string; user: AdminUser } | null>(null); return session ? <Portal token={session.token} user={session.user} onLogout={() => setSession(null)} /> : <Login onLogin={(token, user) => setSession({ token, user })} />; }
createRoot(document.getElementById("root")!).render(<App />);

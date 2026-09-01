import { FormEvent, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AdminUser, get, Home, post } from "./api";
import "./styles.css";

const modules = ["Dashboard", "Plants", "Users", "KYC", "Orders", "Payments", "Support", "Security", "Audit Logs", "System"];
type Session = { access_token: string };

function Login({ onLogin }: { onLogin(token: string, user: AdminUser): void }) {
  const [email, setEmail] = useState(""); const [code, setCode] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { const session = await post<Session>("/admin/auth/verify-totp", { identifier: email, code }); const user = await get<AdminUser>("/me", session.access_token); onLogin(session.access_token, user); }
    catch { setError("Authentication failed."); } finally { setBusy(false); }
  }
  return <main className="login"><section className="loginCard"><Brand label="Secure Administration"/><p className="eyebrow">ADMIN.TRACKMYRMC.COM</p><h1>Privileged access</h1><p>Approved Authority and Central Admin accounts only. Authenticator MFA is required.</p><form onSubmit={submit}><label>Administrator email<input type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} required /></label><label>Authenticator code<input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,8}" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,""))} required /></label>{error && <div className="error" role="alert">{error}</div>}<button disabled={busy}>{busy ? "Verifying…" : "Verify and continue"}</button></form><aside>Sessions remain in protected runtime memory and are never written to browser storage.</aside></section></main>;
}
function Brand({label}:{label:string}) { return <div className="brand"><span>CK</span><div><b>TrackMyRMC</b><small>{label}</small></div></div>; }
function Portal({ token, user, onLogout }: { token: string; user: AdminUser; onLogout(): void }) {
  const [active, setActive] = useState("Dashboard"); const [home, setHome] = useState<Home>(); const [dark, setDark] = useState(true); const [stepUp, setStepUp] = useState(false); const [code, setCode] = useState("");
  useEffect(()=>{ get<Home>("/staff/home", token).then(setHome).catch(onLogout); },[token, onLogout]);
  async function logoutAll(){ await post("/admin/auth/logout-all",{},token).catch(()=>undefined); onLogout(); }
  async function confirmStepUp(event: FormEvent){ event.preventDefault(); await post("/admin/auth/step-up",{code},token); setStepUp(false); setCode(""); }
  return <div className={dark ? "shell dark" : "shell"}><nav><Brand label="Administration"/>{modules.map(item=><button className={active===item?"active":""} onClick={()=>setActive(item)} key={item}>{item}</button>)}</nav><section className="workspace"><header><div><small>SECURE PORTAL</small><h2>{active}</h2></div><div className="account"><button onClick={()=>setDark(v=>!v)}>{dark?"Light":"Dark"}</button><div><b>{user.name}</b><small>{user.role_label}</small></div><button onClick={onLogout}>Logout</button></div></header><main><div className="notice"><b>MFA protected</b><span>High-risk actions require a fresh authenticator challenge and are audit logged.</span><button onClick={()=>setStepUp(true)}>Confirm identity</button></div>{active==="Dashboard"?<><div className="cards">{(home?.kpis||[]).slice(0,4).map(k=><article key={k.label}><small>{k.label}</small><strong>{k.value}</strong></article>)}</div><Panel title="Administration overview">Use the desktop navigation to review existing operational records. Destructive controls are intentionally not introduced by this migration.</Panel></>:<Panel title={active}>This module is separated from the public Android route tree. Existing workflows remain governed by backend RBAC.{active==="Security"&&<button className="danger" onClick={logoutAll}>Revoke all my sessions</button>}</Panel>}</main></section>{stepUp&&<div className="modal"><form onSubmit={confirmStepUp}><h3>Confirm your identity</h3><p>Enter a fresh Authenticator code. Confirmation lasts five minutes.</p><input autoFocus inputMode="numeric" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,""))}/><div><button type="button" onClick={()=>setStepUp(false)}>Cancel</button><button>Verify</button></div></form></div>}</div>;
}
function Panel({title,children}:{title:string;children:React.ReactNode}) { return <section className="panel"><h3>{title}</h3><p>{children}</p></section>; }
function App(){ const [session,setSession]=useState<{token:string;user:AdminUser}|null>(null); return session?<Portal token={session.token} user={session.user} onLogout={()=>setSession(null)}/>:<Login onLogin={(token,user)=>setSession({token,user})}/>; }
createRoot(document.getElementById("root")!).render(<App/>);

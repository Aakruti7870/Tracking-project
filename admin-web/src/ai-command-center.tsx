import { type FormEvent, useState } from "react";
import { post } from "./api";

type Risk = "LOW" | "MEDIUM" | "HIGH" | "DENIED";
type Decision = { command_id: string; intent: string; risk: Risk; status: string; message: string };

export function AICommandCenter({ token, mfaVerified, requestStepUp }: { token: string; mfaVerified: boolean; requestStepUp(): void }) {
  const [prompt, setPrompt] = useState("");
  const [decision, setDecision] = useState<Decision>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setDecision(undefined);
    try {
      setDecision(await post<Decision>("/control-center/ai/commands", { prompt, confirmed: false }, token));
    } catch { setError("Command denied by policy or your current permissions. No action was run."); }
    finally { setBusy(false); }
  }

  return <div className="aiWorkspace">
    <section className="aiHero">
      <p className="eyebrow">POLICY-GATED AI</p><h2>Ask. Understand. Act safely.</h2>
      <p>Every command is permission checked, risk classified, redacted, and audited before a safe backend tool can run.</p>
      <form onSubmit={submit}><label htmlFor="ai-prompt">Administrative command</label><textarea id="ai-prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={1000} minLength={3} placeholder="Why are OTP logins failing today?" required /><div><small>{prompt.length}/1000 · No secrets, OTPs, raw SQL, or production shell</small><button className="primaryButton" disabled={busy || prompt.trim().length < 3}>{busy ? "Checking policy…" : "Analyze command"}</button></div></form>
      {error && <div className="errorBanner" role="alert">{error}</div>}
      {decision && <article className={`aiDecision risk${decision.risk}`}><span>{decision.risk} RISK</span><div><b>{decision.intent.replaceAll("_", " ")}</b><p>{decision.message}</p><small>Audit reference: {decision.command_id}</small></div>{decision.status === "mfa_confirmation_required" && !mfaVerified ? <button className="secondaryButton" onClick={requestStepUp}>Verify MFA</button> : null}</article>}
    </section>
    <section className="aiGuardrails"><h3>Hard guardrails</h3><div>{["No arbitrary SQL", "No production shell", "No secret access", "No OTP visibility", "No permission bypass", "No direct code edits"].map((item) => <span key={item}>✓ {item}</span>)}</div><p>Code changes always follow Incident → Issue → Branch → Tests → PR → Preview → Approval → Merge → Deploy.</p></section>
  </div>;
}

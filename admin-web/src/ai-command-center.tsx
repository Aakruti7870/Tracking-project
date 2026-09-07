import { type FormEvent, useState } from "react";
import { post } from "./api";

type Risk = "LOW" | "MEDIUM" | "HIGH" | "DENIED";
type Decision = { command_id: string; intent: string; risk: Risk; status: string; message: string };

export function AICommandCenter({ token, mfaVerified, requestStepUp }: { token: string; mfaVerified: boolean; requestStepUp(): void }) {
  const [prompt, setPrompt] = useState("");
  const [decision, setDecision] = useState<Decision>();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(confirmed: boolean) {
    setBusy(true); setError("");
    try {
      const payload: Record<string, unknown> = { prompt, confirmed };
      if (confirmed && decision?.risk === "HIGH") payload.reason = reason.trim();
      setDecision(await post<Decision>("/control-center/ai/commands", payload, token));
    } catch {
      setDecision(undefined);
      setError("Command denied by policy or your current permissions. No action was run.");
    } finally { setBusy(false); }
  }

  async function analyze(event: FormEvent) {
    event.preventDefault();
    setDecision(undefined); setReason("");
    await run(false);
  }

  const mediumConfirm = decision?.risk === "MEDIUM" && decision.status === "confirmation_required";
  const highConfirm = decision?.risk === "HIGH" && decision.status === "mfa_confirmation_required";

  return <div className="aiWorkspace">
    <section className="aiHero">
      <p className="eyebrow">POLICY-GATED AI</p><h2>Ask. Understand. Act safely.</h2>
      <p>Every command is permission checked, risk classified, redacted, and audited before a constrained workflow can continue.</p>
      <form onSubmit={analyze}>
        <label htmlFor="ai-prompt">Administrative command</label>
        <textarea id="ai-prompt" value={prompt} onChange={(event) => { setPrompt(event.target.value); setDecision(undefined); setReason(""); }} maxLength={1000} minLength={3} placeholder="Why are OTP logins failing today?" required />
        <div><small>{prompt.length}/1000 · No secrets, .env values, OTPs, passwords, API keys, raw SQL, or production shell</small><button className="primaryButton" disabled={busy || prompt.trim().length < 3}>{busy ? "Checking policy…" : "Analyze command"}</button></div>
      </form>
      {error && <div className="errorBanner" role="alert">{error}</div>}
      {decision && <article className={`aiDecision risk${decision.risk}`}>
        <span>{decision.risk} RISK</span>
        <div><b>{decision.intent.replaceAll("_", " ")}</b><p>{decision.message}</p><small>Audit reference: {decision.command_id}</small></div>
      </article>}

      {mediumConfirm ? <section className="panel">
        <header className="panelHeader"><div><small>SECOND STAGE</small><h3>Confirm draft workflow</h3></div></header>
        <div className="panelBody"><p>This is a draft/workflow request. Review the risk above, then explicitly confirm. The server also requires <code>ai.create_draft</code>.</p><button className="primaryButton" type="button" disabled={busy} onClick={() => void run(true)}>{busy ? "Confirming…" : "Confirm draft"}</button></div>
      </section> : null}

      {highConfirm ? <section className="panel">
        <header className="panelHeader"><div><small>HIGH-RISK SECOND STAGE</small><h3>Reason + fresh MFA + final confirmation</h3></div></header>
        <div className="panelBody">
          <label htmlFor="ai-audit-reason">Audit reason</label>
          <textarea id="ai-audit-reason" value={reason} onChange={(event) => setReason(event.target.value)} minLength={8} maxLength={500} placeholder="Why this privileged workflow is required" />
          {!mfaVerified ? <button className="secondaryButton" type="button" onClick={requestStepUp}>Verify fresh MFA</button> : <span className="stateBadge">Fresh MFA verified</span>}
          <button className="dangerButton" type="button" disabled={busy || !mfaVerified || reason.trim().length < 8} onClick={() => void run(true)}>{busy ? "Confirming…" : "Final confirm"}</button>
        </div>
      </section> : null}
    </section>
    <section className="aiGuardrails"><h3>Hard guardrails</h3><div>{["No arbitrary SQL", "No production shell", "No secret access", "No OTP visibility", "No permission bypass", "No direct code edits"].map((item) => <span key={item}>✓ {item}</span>)}</div><p>DENIED commands never receive a confirmation stage. AI cannot execute shell, SQL, credentials, secrets, arbitrary code, or direct production mutations.</p></section>
  </div>;
}

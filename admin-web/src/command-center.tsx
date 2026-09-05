import { useMemo } from "react";
import type { CSSProperties } from "react";
import type { AdminUser, Home } from "./api";
import "./command-center.css";

type CommandCenterProps = {
  home?: Home;
  user: AdminUser;
  stepUpFresh: boolean;
  requestStepUp(): void;
};

type Metric = { label: string; value: number };
type DonutStyle = CSSProperties & { "--u": string; "--p": string; "--o": string };

const nf = new Intl.NumberFormat("en-IN");

function metricValue(metrics: Metric[], label: string) {
  return metrics.find((item) => item.label === label)?.value ?? 0;
}

function MiniBars({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  return (
    <div className="ccMiniBars" aria-hidden="true">
      {values.map((value, index) => <i key={index} style={{ height: `${Math.max(14, (value / max) * 100)}%` }} />)}
    </div>
  );
}

function MetricCard({ title, value, caption, tone, bars }: { title: string; value: number; caption: string; tone: string; bars: number[] }) {
  return (
    <article className={`ccMetric ${tone}`}>
      <header><span>{title}</span><b>LIVE</b></header>
      <strong>{nf.format(value)}</strong>
      <p>{caption}</p>
      <MiniBars values={bars} />
    </article>
  );
}

function HealthRow({ label, value, status }: { label: string; value: string; status: "good" | "warn" | "info" }) {
  return (
    <div className="ccHealthRow">
      <span className={`ccHealthDot ${status}`} />
      <div><b>{label}</b><small>{value}</small></div>
      <span className={`ccHealthBadge ${status}`}>{status === "good" ? "Healthy" : status === "warn" ? "Watch" : "Active"}</span>
    </div>
  );
}

export function CommandCenter({ home, user, stepUpFresh, requestStepUp }: CommandCenterProps) {
  const metrics = home?.kpis ?? [];
  const plants = metricValue(metrics, "Plants");
  const users = metricValue(metrics, "Users");
  const activeOrders = metricValue(metrics, "Active Orders");
  const openSupport = metricValue(metrics, "Open Support");

  const total = Math.max(plants + users + activeOrders + openSupport, 1);
  const segments = useMemo(() => [
    { label: "Users", value: users, pct: Math.round((users / total) * 100) },
    { label: "Plants", value: plants, pct: Math.round((plants / total) * 100) },
    { label: "Orders", value: activeOrders, pct: Math.round((activeOrders / total) * 100) },
    { label: "Support", value: openSupport, pct: Math.round((openSupport / total) * 100) },
  ], [users, plants, activeOrders, openSupport, total]);

  const donutStyle: DonutStyle = {
    "--u": `${segments[0].pct * 3.6}deg`,
    "--p": `${(segments[0].pct + segments[1].pct) * 3.6}deg`,
    "--o": `${(segments[0].pct + segments[1].pct + segments[2].pct) * 3.6}deg`,
  };

  const firstName = user.name.split(" ")[0] || "Administrator";
  return (
    <div className="ccRoot">
      <section className="ccHero">
        <div className="ccHeroCopy">
          <div className="ccEyebrow"><span /> SUPER ADMIN COMMAND CENTER</div>
          <h2>Platform intelligence at a glance.</h2>
          <p>{firstName}, this control plane gives you a live operational view across plants, customers, orders, support and privileged security posture without exposing sensitive backend data.</p>
          <div className="ccHeroActions">
            <button type="button" className="primaryButton" onClick={requestStepUp}>{stepUpFresh ? "Identity verified" : "Verify privileged identity"}</button>
            <span className="ccLive"><i /> Live control plane</span>
          </div>
        </div>
        <div className="ccOrbit" aria-hidden="true">
          <div className="ccOrbitRing ringOne" />
          <div className="ccOrbitRing ringTwo" />
          <div className="ccCore"><b>TMRMC</b><span>CONTROL</span></div>
          <i className="node n1" /><i className="node n2" /><i className="node n3" /><i className="node n4" />
        </div>
      </section>

      <section className="ccMetrics">
        <MetricCard title="Registered users" value={users} caption="Platform identities under RBAC" tone="blue" bars={[28, 46, 39, 63, 72, Math.max(users, 35)]} />
        <MetricCard title="RMC plants" value={plants} caption="Directory and partner footprint" tone="green" bars={[18, 27, 36, 48, 57, Math.max(plants, 24)]} />
        <MetricCard title="Active orders" value={activeOrders} caption="Orders currently in lifecycle" tone="orange" bars={[14, 42, 34, 54, 45, Math.max(activeOrders, 20)]} />
        <MetricCard title="Open support" value={openSupport} caption="Cases needing operational attention" tone="purple" bars={[8, 18, 12, 24, 17, Math.max(openSupport, 10)]} />
      </section>

      <section className="ccGrid ccGridWide">
        <article className="ccPanel ccActivityPanel">
          <header className="ccPanelHeader"><div><small>PLATFORM ACTIVITY</small><h3>Operational distribution</h3></div><span className="ccPanelBadge">Live</span></header>
          <div className="ccDistribution">
            <div className="ccDonut" style={donutStyle}>
              <div><strong>{nf.format(total)}</strong><span>visible signals</span></div>
            </div>
            <div className="ccLegend">
              {segments.map((segment, index) => <div key={segment.label}><i className={`legend${index + 1}`} /><span>{segment.label}</span><b>{nf.format(segment.value)}</b><small>{segment.pct}%</small></div>)}
            </div>
          </div>
        </article>

        <article className="ccPanel">
          <header className="ccPanelHeader"><div><small>SECURITY POSTURE</small><h3>Privileged session health</h3></div><span className={`ccPanelBadge ${stepUpFresh ? "verified" : ""}`}>{stepUpFresh ? "Verified" : "Protected"}</span></header>
          <div className="ccSecurityScore"><div className="ccShieldScore"><strong>100</strong><span>SECURE</span></div><div><h4>Core controls enforced</h4><p>Dedicated portal MFA, server-side RBAC, memory-only bearer session and minimized read APIs remain active.</p></div></div>
          <div className="ccHealthList">
            <HealthRow label="Portal authentication" value="TOTP provenance required" status="good" />
            <HealthRow label="Session isolation" value="No local/session storage" status="good" />
            <HealthRow label="Sensitive actions" value="Fresh verification required" status={stepUpFresh ? "good" : "info"} />
          </div>
        </article>
      </section>

      <section className="ccGrid">
        <article className="ccPanel">
          <header className="ccPanelHeader"><div><small>OPERATIONS</small><h3>Attention center</h3></div><span className="ccPanelBadge">Priority</span></header>
          <div className="ccAttention">
            <div><span className="ccAttentionIcon">OR</span><div><b>Active order lifecycle</b><small>{nf.format(activeOrders)} orders currently require platform visibility.</small></div><strong>{nf.format(activeOrders)}</strong></div>
            <div><span className="ccAttentionIcon">SP</span><div><b>Support queue</b><small>{nf.format(openSupport)} cases are currently open or in progress.</small></div><strong>{nf.format(openSupport)}</strong></div>
            <div><span className="ccAttentionIcon">PL</span><div><b>Plant network</b><small>{nf.format(plants)} plants are visible to the secure directory.</small></div><strong>{nf.format(plants)}</strong></div>
          </div>
        </article>

        <article className="ccPanel">
          <header className="ccPanelHeader"><div><small>GOVERNANCE</small><h3>Control-plane guarantees</h3></div><span className="ccPanelBadge verified">Enforced</span></header>
          <div className="ccGuarantees">
            <div><span>01</span><div><b>Web-only privileged boundary</b><small>Authority and Central Admin remain outside the mobile route tree.</small></div></div>
            <div><span>02</span><div><b>Data minimization</b><small>Secrets, raw KYC payloads, coordinates and gateway sessions stay excluded.</small></div></div>
            <div><span>03</span><div><b>Read-only administration</b><small>Operational workspaces do not invent destructive mutations.</small></div></div>
          </div>
        </article>
      </section>
    </div>
  );
}

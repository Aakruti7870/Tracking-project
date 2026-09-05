import { useEffect, useMemo, useState } from "react";
import { get } from "./api";
import "./workspaces.css";

export type PortalModule = "Plants" | "Users" | "KYC" | "Orders" | "Payments" | "Support" | "Audit Logs" | "System";

type ListModule = Exclude<PortalModule, "System">;
type Row = Record<string, unknown>;
type Column = { key: string; label: string; format?: (value: unknown, row: Row) => string };
type ListResponse = { items: Row[] };
type SystemResponse = {
  generated_at: string;
  active_sessions: number;
  pending_account_deletions: number;
  automation_workers: { name: string; last_started_at?: string | null; last_success_at?: string | null }[];
};

type WorkspaceConfig = {
  endpoint: string;
  title: string;
  hint: string;
  columns: Column[];
};

const text = (value: unknown) => value === null || value === undefined || value === "" ? "—" : String(value);
const date = (value: unknown) => value ? new Date(String(value)).toLocaleString() : "—";
const number = (value: unknown) => typeof value === "number" ? new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value) : text(value);
const yesNo = (value: unknown) => value === true ? "Yes" : value === false ? "No" : text(value);

const CONFIG: Record<ListModule, WorkspaceConfig> = {
  Plants: {
    endpoint: "/admin/portal/plants",
    title: "Plant directory",
    hint: "Safe operational fields only; contact details and coordinates are intentionally excluded.",
    columns: [
      { key: "name", label: "Plant" }, { key: "city", label: "City" }, { key: "district", label: "District" },
      { key: "status", label: "Status" }, { key: "verified", label: "Verified", format: yesNo }, { key: "created_at", label: "Created", format: date },
    ],
  },
  Users: {
    endpoint: "/admin/portal/users",
    title: "Platform users",
    hint: "Central Admin only. Authentication secrets, identifier hashes and MFA material are never returned.",
    columns: [
      { key: "name", label: "Name" }, { key: "email", label: "Email" }, { key: "phone", label: "Phone" },
      { key: "role", label: "Role" }, { key: "status", label: "Status" }, { key: "created_at", label: "Created", format: date },
    ],
  },
  KYC: {
    endpoint: "/admin/portal/kyc",
    title: "KYC status",
    hint: "Verification state only; Aadhaar/DigiLocker provider payloads and identity documents are not exposed here.",
    columns: [
      { key: "user_id", label: "User ID" }, { key: "purpose", label: "Purpose" }, { key: "status", label: "Status" },
      { key: "updated_at", label: "Updated", format: date },
    ],
  },
  Orders: {
    endpoint: "/admin/portal/orders",
    title: "Order lifecycle",
    hint: "Platform visibility without delivery coordinates, full site address or private contact fields.",
    columns: [
      { key: "order_number", label: "Order" }, { key: "plant_name", label: "Plant" }, { key: "grade", label: "Grade" },
      { key: "quantity", label: "Qty m³", format: number }, { key: "site_name", label: "Site" }, { key: "status", label: "Status" },
      { key: "payment_status", label: "Payment" }, { key: "delivery_date", label: "Delivery" },
    ],
  },
  Payments: {
    endpoint: "/admin/portal/payments",
    title: "Payment control",
    hint: "Read-only payment state. Gateway tokens, sessions and provider response payloads are excluded.",
    columns: [
      { key: "kind", label: "Type" }, { key: "reference", label: "Reference" }, { key: "plant_id", label: "Plant ID" },
      { key: "amount", label: "Amount", format: number }, { key: "method", label: "Method" }, { key: "status", label: "Status" },
      { key: "created_at", label: "Created", format: date },
    ],
  },
  Support: {
    endpoint: "/admin/portal/support",
    title: "Support queue",
    hint: "Case metadata only. Customer conversation bodies remain inside the dedicated audited support-case workflow.",
    columns: [
      { key: "case_number", label: "Case" }, { key: "category", label: "Category" }, { key: "status", label: "Status" },
      { key: "customer_id", label: "Customer ID" }, { key: "order_id", label: "Order ID" }, { key: "created_at", label: "Created", format: date },
    ],
  },
  "Audit Logs": {
    endpoint: "/admin/portal/audit",
    title: "Audit activity",
    hint: "Central Admin only. Raw audit metadata is intentionally withheld from this overview.",
    columns: [
      { key: "created_at", label: "Time", format: date }, { key: "action", label: "Action" }, { key: "actor_id", label: "Actor" },
      { key: "entity_type", label: "Entity" }, { key: "entity_id", label: "Entity ID" },
    ],
  },
};

function DataTable({ rows, columns }: { rows: Row[]; columns: Column[] }) {
  if (!rows.length) return <div className="portalEmpty"><b>No records found</b><span>There is no data to display in this workspace yet.</span></div>;
  return (
    <div className="tableScroll" role="region" aria-label="Administrative data table" tabIndex={0}>
      <table className="adminTable">
        <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => (
          <tr key={text(row.id) !== "—" ? text(row.id) : String(index)}>
            {columns.map((column) => <td key={column.key}>{column.format ? column.format(row[column.key], row) : text(row[column.key])}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function SystemWorkspace({ token }: { token: string }) {
  const [data, setData] = useState<SystemResponse>();
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    setRefreshing(true); setError("");
    try { setData(await get<SystemResponse>("/admin/portal/system", token)); }
    catch { setError("System status could not be loaded. Your session may not have Central Admin access."); }
    finally { setRefreshing(false); }
  }
  useEffect(() => { void load(); }, [token]);

  return (
    <section className="portalWorkspaceCard">
      <header className="workspaceHeader"><div><small>GOVERNANCE</small><h3>System status</h3><p>Operational health metadata only; no deployment secrets or credentials are exposed.</p></div><button className="secondaryButton" type="button" onClick={load} disabled={refreshing}>{refreshing ? "Refreshing…" : "Refresh"}</button></header>
      {error ? <div className="errorBanner" role="alert">{error}</div> : null}
      {data ? <>
        <div className="systemKpis"><article><small>Active sessions</small><strong>{data.active_sessions}</strong></article><article><small>Pending deletions</small><strong>{data.pending_account_deletions}</strong></article><article><small>Workers</small><strong>{data.automation_workers.length}</strong></article></div>
        <div className="workerList">{data.automation_workers.length ? data.automation_workers.map((worker) => <article key={worker.name}><b>{worker.name}</b><span>Last success: {date(worker.last_success_at)}</span><small>Last started: {date(worker.last_started_at)}</small></article>) : <div className="portalEmpty"><b>No worker heartbeat rows</b><span>The worker collection has no current records.</span></div>}</div>
        <p className="workspaceTimestamp">Generated {date(data.generated_at)}</p>
      </> : !error ? <div className="workspaceLoading">Loading secure system status…</div> : null}
    </section>
  );
}

function ListWorkspace({ module, token }: { module: ListModule; token: string }) {
  const config = CONFIG[module];
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  async function load() {
    setLoading(true); setError("");
    try { const result = await get<ListResponse>(config.endpoint, token); setRows(result.items || []); }
    catch { setRows([]); setError("This secure workspace could not be loaded. Confirm your administrator role and session."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [config.endpoint, token]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) => Object.values(row).some((value) => text(value).toLowerCase().includes(needle)));
  }, [query, rows]);

  return (
    <section className="portalWorkspaceCard">
      <header className="workspaceHeader"><div><small>READ-ONLY CONTROL PLANE</small><h3>{config.title}</h3><p>{config.hint}</p></div><button className="secondaryButton" type="button" onClick={load} disabled={loading}>{loading ? "Loading…" : "Refresh"}</button></header>
      <div className="workspaceToolbar"><label htmlFor={`portal-search-${module.replace(/\s/g, "-").toLowerCase()}`}>Search visible records</label><input id={`portal-search-${module.replace(/\s/g, "-").toLowerCase()}`} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${module.toLowerCase()}…`} /></div>
      {error ? <div className="errorBanner" role="alert">{error}</div> : loading ? <div className="workspaceLoading">Loading server-authorized data…</div> : <DataTable rows={visible} columns={config.columns} />}
      {!loading && !error ? <p className="workspaceTimestamp">Showing {visible.length} of {rows.length} latest records. Read-only administrative view.</p> : null}
    </section>
  );
}

export function DataWorkspace({ module, token }: { module: PortalModule; token: string }) {
  return module === "System" ? <SystemWorkspace token={token} /> : <ListWorkspace module={module} token={token} />;
}

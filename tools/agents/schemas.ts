export const ROLES = ["kimi", "deepseek", "laguna", "gemma"] as const;
export type AgentRole = (typeof ROLES)[number];

export type AgentResult = {
  summary: string;
  findings: Array<{ severity: "info" | "warning" | "error"; file?: string; detail: string }>;
  recommendations: string[];
  verification: string[];
  limitations: string[];
};

export const EMPTY_RESULT: AgentResult = {
  summary: "No usable analysis was returned.",
  findings: [], recommendations: [], verification: [], limitations: []
};

function strings(value: unknown, limit = 12): string[] {
  return Array.isArray(value) ? value.filter((x): x is string => typeof x === "string").slice(0, limit) : [];
}

export function parseAgentResult(raw: string): AgentResult {
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/i)?.[1];
  let value: any;
  try { value = JSON.parse(fenced ?? raw); } catch { return { ...EMPTY_RESULT, summary: raw.trim().slice(0, 600) || EMPTY_RESULT.summary, limitations: ["Response was not valid JSON."] }; }
  return {
    summary: typeof value?.summary === "string" ? value.summary.slice(0, 600) : EMPTY_RESULT.summary,
    findings: Array.isArray(value?.findings) ? value.findings.slice(0, 12).flatMap((item: any) => {
      if (!item || typeof item.detail !== "string") return [];
      const severity = ["info", "warning", "error"].includes(item.severity) ? item.severity : "info";
      return [{ severity, ...(typeof item.file === "string" ? { file: item.file.slice(0, 300) } : {}), detail: item.detail.slice(0, 1000) }];
    }) : [],
    recommendations: strings(value?.recommendations),
    verification: strings(value?.verification),
    limitations: strings(value?.limitations)
  };
}

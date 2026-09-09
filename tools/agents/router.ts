#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { analyze, validateModel } from "./nvidia-client.ts";
import { ROLES, type AgentRole } from "./schemas.ts";

const CONFIG: Record<AgentRole, { env: string; specialty: string }> = {
  kimi: { env: "KIMI_MODEL", specialty: "repository architecture and large-context analysis" },
  deepseek: { env: "DEEPSEEK_MODEL", specialty: "complex coding, backend, security, and debugging analysis" },
  laguna: { env: "LAGUNA_MODEL", specialty: "CI, build, test, and log analysis" },
  gemma: { env: "GEMMA_MODEL", specialty: "frontend and UI review" }
};

export function chooseRole(task: string): AgentRole {
  if (/\b(ci|build|test|log|workflow|pipeline|compiler|lint)\b/i.test(task)) return "laguna";
  if (/\b(ui|ux|frontend|react|css|accessibility|screen|layout)\b/i.test(task)) return "gemma";
  if (/\b(security|backend|api|database|debug|bug|algorithm|auth)\b/i.test(task)) return "deepseek";
  return "kimi";
}

function arg(name: string): string | undefined { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] : undefined; }

async function stdin(): Promise<string> {
  if (process.stdin.isTTY) return "";
  let value = ""; for await (const chunk of process.stdin) value += chunk;
  return value;
}

async function main() {
  if (process.argv.includes("--validate")) {
    const results: Record<string, string> = {};
    for (const role of ROLES) {
      const model = process.env[CONFIG[role].env];
      if (!model) { results[role] = `not configured (${CONFIG[role].env})`; continue; }
      try { await validateModel(model); results[role] = "available"; } catch (error) { results[role] = error instanceof Error ? error.message : String(error); }
    }
    console.log(JSON.stringify(results, null, 2)); return;
  }
  let task = arg("--task") ?? await stdin();
  if (!task.trim()) throw new Error("Provide a task with --task or stdin");
  const file = arg("--file");
  if (file) {
    if (/(^|\/)(\.env|\.git|\.agent-cache)(\/|$)|credential|secret|\.pem$|\.key$/i.test(file)) throw new Error("Refusing to read a sensitive path");
    const content = await readFile(file, "utf8");
    task += `\n\nRelevant file (${file}, truncated):\n${content.slice(0, 60_000)}`;
  }
  const requested = arg("--role");
  if (requested && !ROLES.includes(requested as AgentRole)) throw new Error(`Unknown role: ${requested}`);
  const primary = (requested as AgentRole | undefined) ?? chooseRole(task);
  const candidates = [primary, ...ROLES.filter(role => role !== primary)];
  const failures: string[] = [];
  for (const role of candidates) {
    const model = process.env[CONFIG[role].env];
    if (!model) { failures.push(`${role}: model not configured`); continue; }
    try {
      const system = `You are a read-only ${CONFIG[role].specialty} advisor. Never request or reveal secrets. Do not edit, commit, push, merge, or claim to run commands. Return ONLY concise JSON with keys summary, findings (severity, optional file, detail), recommendations, verification, limitations. Maximum 12 findings. Give evidence and leave all implementation decisions to Codex.`;
      console.log(JSON.stringify({ role, model, result: await analyze(model, system, task) }, null, 2)); return;
    } catch (error) { failures.push(`${role}: ${error instanceof Error ? error.message : String(error)}`); }
  }
  throw new Error(`No external agent succeeded. Safe local fallback required. ${failures.join("; ")}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch(error => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1; });
}

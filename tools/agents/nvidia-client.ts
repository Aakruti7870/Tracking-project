import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import type { AgentResult } from "./schemas.ts";
import { parseAgentResult } from "./schemas.ts";

const BASE_URL = process.env.NVIDIA_API_BASE_URL ?? "https://integrate.api.nvidia.com/v1";
const CACHE_DIR = path.resolve(".agent-cache");
const RETRYABLE = new Set([408, 429, 500, 502, 503, 504]);
let lastRequest = 0;
let modelIdsPromise: Promise<Set<string>> | undefined;

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function request(endpoint: string, init: RequestInit, retries = 2): Promise<Response> {
  const key = process.env.NVIDIA_API_KEY;
  if (!key) throw new Error("NVIDIA_API_KEY is not configured");
  for (let attempt = 0; ; attempt++) {
    const delay = Math.max(0, 350 - (Date.now() - lastRequest));
    if (delay) await sleep(delay);
    lastRequest = Date.now();
    try {
      const response = await fetch(`${BASE_URL}${endpoint}`, {
        ...init,
        headers: { "accept": "application/json", "content-type": "application/json", authorization: `Bearer ${key}`, ...init.headers },
        signal: AbortSignal.timeout(Number(process.env.AGENT_TIMEOUT_MS ?? 45_000))
      });
      if (response.ok || !RETRYABLE.has(response.status) || attempt >= retries) return response;
      await sleep(Math.min(4_000, 500 * 2 ** attempt + Math.random() * 250));
    } catch (error) {
      if (attempt >= retries) throw error;
      await sleep(Math.min(4_000, 500 * 2 ** attempt));
    }
  }
}

export async function availableModelIds(): Promise<Set<string>> {
  modelIdsPromise ??= (async () => {
    const response = await request("/models", { method: "GET", headers: { "content-type": "application/json" } });
    if (!response.ok) throw new Error(`NVIDIA models API returned HTTP ${response.status}`);
    const body: any = await response.json();
    return new Set((Array.isArray(body?.data) ? body.data : []).map((model: any) => model?.id).filter(Boolean));
  })();
  try { return await modelIdsPromise; } catch (error) { modelIdsPromise = undefined; throw error; }
}

export async function validateModel(model: string): Promise<void> {
  if (!(await availableModelIds()).has(model)) throw new Error(`Configured model is unavailable from NVIDIA: ${model}`);
}

export async function analyze(model: string, system: string, task: string): Promise<AgentResult> {
  await validateModel(model);
  const cacheKey = createHash("sha256").update(JSON.stringify({ model, system, task })).digest("hex");
  const cacheFile = path.join(CACHE_DIR, `${cacheKey}.json`);
  try { return JSON.parse(await readFile(cacheFile, "utf8")); } catch {}
  const response = await request("/chat/completions", {
    method: "POST",
    body: JSON.stringify({ model, temperature: 0.1, max_tokens: 1200, messages: [{ role: "system", content: system }, { role: "user", content: task }] })
  });
  if (!response.ok) throw new Error(`NVIDIA completion API returned HTTP ${response.status}`);
  const body: any = await response.json();
  const content = body?.choices?.[0]?.message?.content;
  if (typeof content !== "string") throw new Error("NVIDIA returned no textual completion");
  const result = parseAgentResult(content);
  await mkdir(CACHE_DIR, { recursive: true });
  await writeFile(cacheFile, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
  return result;
}

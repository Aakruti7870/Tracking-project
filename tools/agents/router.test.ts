import assert from "node:assert/strict";
import test from "node:test";
import { chooseRole } from "./router.ts";
import { parseAgentResult } from "./schemas.ts";

test("routes specialties", () => {
  assert.equal(chooseRole("review the repository architecture"), "kimi");
  assert.equal(chooseRole("debug backend auth security"), "deepseek");
  assert.equal(chooseRole("diagnose CI build logs"), "laguna");
  assert.equal(chooseRole("review React UI accessibility"), "gemma");
});

test("normalizes structured responses", () => {
  const result = parseAgentResult('{"summary":"ok","findings":[{"severity":"error","detail":"broken"}],"recommendations":["fix"]}');
  assert.equal(result.summary, "ok"); assert.equal(result.findings[0]?.severity, "error");
});

test("safely handles non-JSON responses", () => {
  assert.match(parseAgentResult("plain response").limitations[0], /not valid JSON/);
});

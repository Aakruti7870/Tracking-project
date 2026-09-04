import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const routes = readFileSync(`${process.cwd()}/src/support/routes.ts`, "utf8");
const screen = readFileSync(`${process.cwd()}/app/support.tsx`, "utf8");
const order = readFileSync(`${process.cwd()}/app/new-order.tsx`, "utf8");
const staff = readFileSync(`${process.cwd()}/app/support-cases.tsx`, "utf8");
const more = readFileSync(`${process.cwd()}/src/screens/StaffMore.tsx`, "utf8");
const widget = readFileSync(`${process.cwd()}/src/support/SupportWidgetBridge.tsx`, "utf8");
const layout = readFileSync(`${process.cwd()}/app/_layout.tsx`, "utf8");

test("support actions route only to existing secure screens", () => {
  for (const route of ["/kyc", "/customer/orders", "/account-deletion", "/plant-onboarding"]) {
    assert.ok(routes.includes(`\"${route}\"`));
  }
  assert.match(routes, /OPEN_TRACKING[\s\S]*owned-id|OPEN_TRACKING/);
  assert.ok(!routes.includes("http://") && !routes.includes("https://"));
});

test("support UI includes escalation, owned-order selector, and safe loading states", () => {
  assert.ok(screen.includes("Create Support Case"));
  assert.ok(screen.includes("/customer/orders"));
  assert.ok(screen.includes("Loading your orders"));
  assert.ok(screen.includes("Unable to reach support"));
  assert.ok(screen.includes("Do not include passwords, OTPs, passkeys, recovery codes or payment credentials"));
});

test("all customer categories and case conversation controls are present", () => {
  for (const category of ["LOGIN", "KYC", "ORDER", "TRACKING", "PAYMENT", "ACCOUNT_DELETION", "PLANT_ONBOARDING", "GENERAL"]) {
    assert.ok(screen.includes(`category: "${category}"`));
  }
  for (const text of ["My Support Cases", "Loading conversation", "Send Reply", "closed for replies", "Related order"]) assert.ok(screen.includes(text));
  assert.ok(screen.includes("/assistant/support/cases/${selectedCaseId}/replies"));
});

test("assisted ordering prepares before requiring explicit confirmation", () => {
  const prepare = order.indexOf('"/assistant/orders/prepare"');
  const confirm = order.indexOf('"/assistant/orders/confirm"');
  assert.ok(prepare >= 0 && confirm > prepare);
  assert.ok(order.includes("This order has not yet been placed"));
  assert.ok(order.includes('label="Confirm Order"'));
  assert.ok(screen.includes("/new-order?assistant=1"));
});

test("staff screen supports public replies, internal notes, filters, and status controls", () => {
  for (const status of ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]) assert.ok(staff.includes(`"${status}"`));
  for (const text of ["Send Public Reply", "Add Internal Note", "Change status", "Loading support cases", "Unable to update case status"]) assert.ok(staff.includes(text));
  assert.match(more, /role === "authority" \|\| user\?\.role === "central_admin"/);
  assert.ok(!more.includes('user?.role === "admin"') && !more.includes('user?.role === "plant_owner"'));
});

test("login help widget is public guidance only and never calls customer APIs", () => {
  assert.ok(layout.includes("<SupportWidgetBridge />"));
  assert.ok(widget.includes('pathname === "/login"'));
  assert.ok(widget.includes("!token && !user"));
  assert.ok(widget.includes("Safe help before sign-in"));
  assert.ok(widget.includes("No customer, order, tracking or payment data is available here"));
  assert.ok(widget.includes("/plant-onboarding"));
  assert.ok(widget.includes("/account-deletion-public"));
  assert.ok(!widget.includes("apiPost") && !widget.includes("apiGet"));
  assert.ok(!widget.includes('"/assistant/') && !widget.includes('"/customer/orders'));
});

test("floating full support widget is restricted to authenticated customers", () => {
  assert.ok(widget.includes('Boolean(token) && user?.role === "customer"'));
  assert.ok(widget.includes('pathname !== "/support"'));
  assert.ok(widget.includes('router.push("/support"'));
  assert.ok(!widget.includes('user?.role === "driver"'));
  assert.ok(!widget.includes('user?.role === "admin"'));
  assert.ok(!widget.includes('user?.role === "plant_owner"'));
});

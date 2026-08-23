import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), "utf8");
const roleRoutes = read("src/auth/roleRoutes.ts");
const login = read("app/login.tsx");
const index = read("app/index.tsx");

const expectedRoutes = {
  customer: "/customer",
  plant_owner: "/owner",
  driver: "/driver",
  admin: "/admin",
  dispatcher: "/dispatcher",
  operator: "/operator",
  supervisor: "/supervisor",
  accountant: "/accountant",
  quality_engineer: "/quality_engineer",
  fleet_manager: "/fleet_manager",
  store_manager: "/store_manager",
  authority: "/authority",
  central_admin: "/central_admin",
};

const failures = [];

for (const [role, route] of Object.entries(expectedRoutes)) {
  const expected = `${role}: \"${route}\"`;
  if (!roleRoutes.includes(expected)) {
    failures.push(`Missing role route: ${role} -> ${route}`);
  }
}

if (!login.includes("router.replace(roleRouteFor(me.role) as any)")) {
  failures.push("Successful OTP verification must route directly using me.role");
}

if (login.includes("router.replace(\"/\")")) {
  failures.push("Login must not route successful OTP verification through /");
}

if (!login.includes("if (!hydrating && token && user)")) {
  failures.push("Login must redirect an already authenticated session");
}

if (!index.includes("roleRouteFor(user.role)")) {
  failures.push("Cold-start routing must use the shared role route helper");
}

if (failures.length) {
  console.error("Auth routing regression check failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Auth routing regression check passed for all 13 roles.");

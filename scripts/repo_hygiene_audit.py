#!/usr/bin/env python3
"""Deterministic repository-hygiene audit for TrackMyRMC.

This scanner is intentionally conservative: it reports only source-controlled
cleanup candidates and separates framework conventions / intentional route
overrides so they are not mistaken for dead code.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path.cwd()
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"
REPORT_MD = ROOT / "repo-hygiene-report.md"
REPORT_JSON = ROOT / "repo-hygiene-report.json"

SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
TEXT_SUFFIXES = SOURCE_SUFFIXES | {".json", ".yml", ".yaml", ".md", ".txt", ".sh", ".html", ".css"}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
PLATFORM_MARKERS = (".web.", ".native.", ".android.", ".ios.")

# These files are loaded by Expo/Metro/Docker/convention rather than normal TS imports.
FRAMEWORK_FILES = {
    "frontend/legacy-service-worker.js",
    "frontend/metro.config.js",
    "frontend/plugins/with-play-store-compatibility.js",
    "frontend/src/utils/storage/index.web.ts",
    "frontend/src/components/PlantMap.web.tsx",
    "frontend/src/payments/cashfree.web.ts",
}

# Listing/source assets intentionally not imported by the application bundle.
MANUAL_ASSETS = {"frontend/assets/images/play-store-icon.png"}

# Expo / RN runtime dependencies may be consumed by framework configuration or peers.
FRAMEWORK_DEPS = {
    "@expo/metro-runtime",
    "expo-system-ui",
    "react-dom",
    "react-native-screens",
    "react-native-web",
    "react-native-worklets",
}

# Exact duplicate routes that are intentionally ordered in backend/server.py.
INTENTIONAL_ROUTE_OVERRIDES = {
    ("POST", "/api/auth/request-otp"),
    ("POST", "/api/auth/verify-otp"),
    ("POST", "/api/auth/staff/request-otp"),
    ("POST", "/api/auth/staff/verify-otp"),
    ("GET", "/api/customer/kyc"),
    ("PUT", "/api/ops/plants/{plant_id}/payroll"),
    ("PUT", "/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/draft"),
    ("POST", "/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/mark-paid"),
    ("POST", "/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/owner-decision"),
}


def git_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"])
    return [ROOT / item.decode() for item in raw.split(b"\0") if item]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def duplicate_content(files: list[Path]) -> tuple[list[dict], list[dict]]:
    groups: dict[tuple[int, str], list[str]] = defaultdict(list)
    for path in files:
        try:
            size = path.stat().st_size
            if size:
                groups[(size, digest(path))].append(rel(path))
        except OSError:
            pass

    intentional, candidates = [], []
    for (size, sha), paths in groups.items():
        if len(paths) < 2:
            continue
        item = {"size": size, "sha256": sha, "paths": sorted(paths)}
        # Tiny Expo Router files often intentionally re-export a shared screen.
        if size <= 512 and all(p.startswith("frontend/app/") for p in paths):
            intentional.append(item)
        else:
            candidates.append(item)
    key = lambda x: (-x["size"], x["paths"])
    return sorted(candidates, key=key), sorted(intentional, key=key)


def generated_candidates(files: list[Path]) -> list[str]:
    exact = {
        ".gitconfig",
        "BUILD_REPORT.md",
        "PRODUCTION_READINESS_REPORT.md",
        "active_track_order.txt",
    }
    suffixes = (".bak", ".backup", ".orig", ".tmp", ".log", ".rej")
    result = []
    for path in files:
        p = rel(path)
        if p.endswith("/.gitkeep") or p in {"test_result.md", "memory/PRD.md"} or p.startswith(".emergent/"):
            continue
        if p in exact or (p.startswith("test_reports/") and not p.endswith(".gitkeep")) or p.lower().endswith(suffixes):
            result.append(p)
    return sorted(result)


def sensitive_filename_candidates(files: list[Path]) -> list[str]:
    # google-services.json is Firebase client configuration; secret/signing guards
    # separately scan actual private key / credential material.
    pattern = re.compile(r"(^|/)(\.env($|\.)|.*\.(pem|key|p12|pfx|jks|keystore)$)", re.I)
    return sorted(rel(p) for p in files if pattern.search(rel(p)))


def frontend_text_files(files: list[Path]) -> list[Path]:
    return [p for p in files if rel(p).startswith("frontend/") and p.suffix.lower() in TEXT_SUFFIXES]


def resolve_import(importer: Path, spec: str) -> set[Path]:
    if spec.startswith("@/"):
        base = FRONTEND / spec[2:]
    elif spec.startswith(("./", "../")):
        base = importer.parent / spec
    else:
        return set()

    candidates: list[Path] = [base]
    if not base.suffix:
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            candidates.append(base.with_suffix(ext))
        for platform in ("web", "native", "android", "ios"):
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                candidates.append(base.with_name(f"{base.name}.{platform}{ext}"))
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            candidates.append(base / f"index{ext}")
        for platform in ("web", "native", "android", "ios"):
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                candidates.append(base / f"index.{platform}{ext}")

    found: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(ROOT.resolve())
        except Exception:
            continue
        if resolved.is_file():
            found.add(resolved)
    return found


def frontend_orphans(files: list[Path]) -> list[str]:
    import_re = re.compile(
        r"(?:from\s+|import\s*\(|require\s*\()\s*[\"']([^\"']+)[\"']|^\s*import\s*[\"']([^\"']+)[\"']",
        re.M,
    )
    referenced: set[Path] = set()
    for importer in frontend_text_files(files):
        for match in import_re.finditer(read_text(importer)):
            spec = match.group(1) or match.group(2)
            referenced.update(resolve_import(importer, spec))

    result = []
    for path in files:
        p = rel(path)
        if not p.startswith("frontend/src/") or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if p in FRAMEWORK_FILES or any(marker in path.name for marker in PLATFORM_MARKERS):
            continue
        if "/__tests__/" in p or re.search(r"\.(test|spec)\.[jt]sx?$", p):
            continue
        if path.name.startswith("index."):
            continue
        if path.resolve() not in referenced:
            result.append(p)
    return sorted(result)


def unreferenced_assets(files: list[Path]) -> list[str]:
    text = "\n".join(read_text(p) for p in frontend_text_files(files) if p.name != "package-lock.json")
    result = []
    for asset in files:
        p = rel(asset)
        if not p.startswith("frontend/assets/") or asset.suffix.lower() not in ASSET_SUFFIXES or p in MANUAL_ASSETS:
            continue
        frontend_rel = p.removeprefix("frontend/")
        if not any(token in text for token in (asset.name, frontend_rel, "../" + frontend_rel, "@/" + frontend_rel)):
            result.append(p)
    return sorted(result)


def unused_frontend_dependencies(files: list[Path]) -> list[str]:
    package = json.loads(read_text(FRONTEND / "package.json") or "{}")
    deps = sorted((package.get("dependencies") or {}).keys())
    import_re = re.compile(
        r"(?:from\s+|import\s*\(|require\s*\()\s*[\"']([^\"']+)[\"']|^\s*import\s*[\"']([^\"']+)[\"']",
        re.M,
    )
    specs: set[str] = set()
    for path in frontend_text_files(files):
        for match in import_re.finditer(read_text(path)):
            specs.add(match.group(1) or match.group(2))
    config = read_text(FRONTEND / "app.json") + read_text(FRONTEND / "app.config.js")
    return [
        dep for dep in deps
        if dep not in FRAMEWORK_DEPS
        and dep not in config
        and not any(spec == dep or spec.startswith(dep + "/") for spec in specs)
    ]


def backend_imports(files: list[Path]) -> set[str]:
    imports: set[str] = set()
    for path in files:
        p = rel(path)
        if not p.startswith("backend/") or path.suffix != ".py":
            continue
        try:
            tree = ast.parse(read_text(path), filename=p)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
                imports.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def backend_orphans(files: list[Path]) -> list[str]:
    imports = backend_imports(files)
    protected = {"server.py", "config.py", "database.py", "models.py", "__init__.py"}
    result = []
    for path in files:
        p = rel(path)
        if not p.startswith("backend/") or path.suffix != ".py" or "/tests/" in p or path.name.startswith("test_") or path.name in protected:
            continue
        module = path.relative_to(BACKEND).with_suffix("").as_posix().replace("/", ".")
        basename = module.split(".")[-1]
        if not any(i == module or i.startswith(module + ".") or i == basename for i in imports):
            result.append(p)
    return sorted(result)


def duplicate_api_routes(files: list[Path]) -> tuple[list[dict], list[dict]]:
    prefix_re = re.compile(r"APIRouter\s*\([^)]*?prefix\s*=\s*[\"']([^\"']*)[\"']", re.S)
    route_re = re.compile(r"@(?:router|app)\.(get|post|put|patch|delete)\s*\(\s*[\"']([^\"']+)[\"']", re.I)
    routes: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in files:
        p = rel(path)
        if not p.startswith("backend/") or path.suffix != ".py":
            continue
        source = read_text(path)
        match = prefix_re.search(source)
        prefix = match.group(1) if match else ""
        for method, route in route_re.findall(source):
            full = (prefix.rstrip("/") + "/" + route.lstrip("/")) if prefix else route
            routes[(method.upper(), full if full.startswith("/") else "/" + full)].add(p)

    intentional, candidates = [], []
    for (method, route), paths in routes.items():
        if len(paths) < 2:
            continue
        item = {"method": method, "route": route, "files": sorted(paths)}
        (intentional if (method, route) in INTENTIONAL_ROUTE_OVERRIDES else candidates).append(item)
    key = lambda x: (x["route"], x["method"])
    return sorted(candidates, key=key), sorted(intentional, key=key)


def write_section(lines: list[str], title: str, values, formatter=None) -> None:
    lines.extend([f"## {title}", ""])
    if not values:
        lines.extend(["None detected.", ""])
        return
    for value in values:
        lines.append(formatter(value) if formatter else f"- `{value}`")
    lines.append("")


def main() -> int:
    files = git_files()
    duplicate_candidates, intentional_stubs = duplicate_content(files)
    route_candidates, intentional_routes = duplicate_api_routes(files)
    data = {
        "tracked_files": len(files),
        "generated_or_runtime_candidates": generated_candidates(files),
        "sensitive_filename_candidates": sensitive_filename_candidates(files),
        "frontend_potential_orphan_modules": frontend_orphans(files),
        "frontend_unreferenced_asset_candidates": unreferenced_assets(files),
        "frontend_potential_unused_dependencies": unused_frontend_dependencies(files),
        "backend_potential_orphan_modules": backend_orphans(files),
        "duplicate_api_route_candidates": route_candidates,
        "intentional_api_route_overrides": intentional_routes,
        "duplicate_content_candidates": duplicate_candidates,
        "intentional_route_stub_duplicates": intentional_stubs,
    }
    REPORT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")

    lines = [
        "# Repository Hygiene Audit",
        "",
        "> Conservative static scan. Candidates still require build/test/runtime proof before deletion.",
        "",
        f"Tracked files: **{len(files)}**",
        "",
    ]
    write_section(lines, "Generated / runtime / stale artifact candidates", data["generated_or_runtime_candidates"])
    write_section(lines, "Tracked sensitive-filename candidates", data["sensitive_filename_candidates"])
    write_section(lines, "Potential frontend orphan modules", data["frontend_potential_orphan_modules"])
    write_section(lines, "Potential unreferenced frontend assets", data["frontend_unreferenced_asset_candidates"])
    write_section(lines, "Potential unused frontend dependencies", data["frontend_potential_unused_dependencies"])
    write_section(lines, "Potential backend orphan modules", data["backend_potential_orphan_modules"])
    fmt_route = lambda x: f"- `{x['method']} {x['route']}` — " + ", ".join(f"`{p}`" for p in x["files"])
    write_section(lines, "Duplicate API route candidates", data["duplicate_api_route_candidates"], fmt_route)
    write_section(lines, "Intentional ordered API overrides / compatibility guards", data["intentional_api_route_overrides"], fmt_route)
    fmt_dup = lambda x: f"- **{x['size']} bytes** `{x['sha256'][:12]}` — " + ", ".join(f"`{p}`" for p in x["paths"])
    write_section(lines, "Duplicate content candidates", data["duplicate_content_candidates"][:100], fmt_dup)
    write_section(lines, "Intentional tiny Expo route-wrapper duplicates", data["intentional_route_stub_duplicates"][:100], fmt_dup)
    lines.extend([
        "## Cleanup rule",
        "",
        "Delete only candidates proven redundant/unreachable by CI and runtime routing. Production/customer/database records are outside this repository cleanup.",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT_MD.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

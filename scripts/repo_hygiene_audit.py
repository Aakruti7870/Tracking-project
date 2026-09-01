#!/usr/bin/env python3
"""Read-only repository hygiene audit.

The scanner intentionally reports candidates rather than deleting anything.
It uses only the Python standard library so it can run deterministically in CI.
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

TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".yml", ".yaml",
    ".md", ".txt", ".sh", ".html", ".css", ".toml", ".ini", ".cfg", ".properties",
}
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


def git_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files", "-z"])
    return [ROOT / p.decode("utf-8") for p in out.split(b"\0") if p]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def duplicate_groups(files: list[Path]) -> list[dict]:
    groups: dict[tuple[int, str], list[str]] = defaultdict(list)
    for path in files:
        try:
            size = path.stat().st_size
            if size == 0:
                continue
            groups[(size, sha256(path))].append(rel(path))
        except OSError:
            pass
    result = []
    for (size, digest), paths in groups.items():
        if len(paths) > 1:
            result.append({"size": size, "sha256": digest, "paths": sorted(paths)})
    return sorted(result, key=lambda x: (-x["size"], x["paths"]))


def generated_candidates(files: list[Path]) -> list[str]:
    exact = {
        ".gitconfig",
        "BUILD_REPORT.md",
        "PRODUCTION_READINESS_REPORT.md",
        "active_track_order.txt",
        "test_result.md",
        ".emergent/cron/applied.hash",
        ".emergent/markers/.bootstrap-complete",
        ".emergent/markers/.restore-complete",
    }
    prefixes = ("test_reports/", "memory/")
    suffixes = (".bak", ".backup", ".orig", ".tmp", ".log", ".rej")
    candidates = []
    for path in files:
        p = rel(path)
        if p in exact or p.startswith(prefixes) or p.lower().endswith(suffixes):
            candidates.append(p)
    return sorted(candidates)


def sensitive_filename_candidates(files: list[Path]) -> list[str]:
    pattern = re.compile(r"(^|/)(\.env($|\.)|.*\.(pem|key|p12|pfx|jks|keystore)$|google-services\.json$)", re.I)
    return sorted(rel(p) for p in files if pattern.search(rel(p)))


def frontend_text_files(files: list[Path]) -> list[Path]:
    return [
        p for p in files
        if rel(p).startswith("frontend/")
        and p.suffix.lower() in TEXT_SUFFIXES
        and "/node_modules/" not in rel(p)
        and "/dist/" not in rel(p)
    ]


def resolve_frontend_import(importer: Path, spec: str) -> Path | None:
    if spec.startswith("@/"):
        base = FRONTEND / spec[2:]
    elif spec.startswith("./") or spec.startswith("../"):
        base = importer.parent / spec
    else:
        return None

    candidates = [base]
    if base.suffix == "":
        candidates.extend(base.with_suffix(ext) for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"))
        candidates.extend(base / f"index{ext}" for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"))
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
            candidate.relative_to(ROOT.resolve())
        except Exception:
            continue
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def frontend_orphans(files: list[Path]) -> list[str]:
    text_files = frontend_text_files(files)
    import_re = re.compile(
        r"(?:from\s+|import\s*\(|require\s*\()\s*[\"']([^\"']+)[\"']|^\s*import\s*[\"']([^\"']+)[\"']",
        re.M,
    )
    referenced: set[Path] = set()
    for importer in text_files:
        text = read_text(importer)
        for match in import_re.finditer(text):
            spec = match.group(1) or match.group(2)
            resolved = resolve_frontend_import(importer, spec)
            if resolved:
                referenced.add(resolved)

    candidates = []
    for path in files:
        p = rel(path)
        if not p.startswith("frontend/src/") or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if "/__tests__/" in p or p.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
            continue
        if path.name.startswith("index."):
            continue
        if path.resolve() not in referenced:
            candidates.append(p)
    return sorted(candidates)


def frontend_unreferenced_assets(files: list[Path]) -> list[str]:
    assets = [p for p in files if rel(p).startswith("frontend/assets/") and p.suffix.lower() in ASSET_SUFFIXES]
    text_paths = [p for p in frontend_text_files(files) if p.name not in {"package-lock.json"}]
    haystack = "\n".join(read_text(p) for p in text_paths)
    candidates = []
    for asset in assets:
        p = rel(asset)
        frontend_rel = p.removeprefix("frontend/")
        checks = {
            asset.name,
            frontend_rel,
            "../" + frontend_rel,
            "@/" + frontend_rel,
        }
        if not any(token in haystack for token in checks):
            candidates.append(p)
    return sorted(candidates)


def frontend_unused_dependencies(files: list[Path]) -> list[str]:
    package_json = json.loads(read_text(FRONTEND / "package.json") or "{}")
    deps = sorted((package_json.get("dependencies") or {}).keys())
    import_re = re.compile(
        r"(?:from\s+|import\s*\(|require\s*\()\s*[\"']([^\"']+)[\"']|^\s*import\s*[\"']([^\"']+)[\"']",
        re.M,
    )
    specs: set[str] = set()
    for path in frontend_text_files(files):
        if path.name in {"package.json", "package-lock.json"}:
            continue
        for m in import_re.finditer(read_text(path)):
            specs.add(m.group(1) or m.group(2))
    config_text = "\n".join(
        read_text(p) for p in [FRONTEND / "app.json", FRONTEND / "app.config.js"] if p.exists()
    )
    candidates = []
    for dep in deps:
        used = any(spec == dep or spec.startswith(dep + "/") for spec in specs) or dep in config_text
        if not used:
            candidates.append(dep)
    return candidates


def backend_module_name(path: Path) -> tuple[str, str]:
    relative = path.relative_to(BACKEND).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    short = ".".join(parts)
    return (f"backend.{short}" if short else "backend", short)


def backend_imports(files: list[Path]) -> set[str]:
    imported: set[str] = set()
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
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module)
                    for alias in node.names:
                        imported.add(f"{node.module}.{alias.name}")
    return imported


def backend_orphans(files: list[Path]) -> list[str]:
    imports = backend_imports(files)
    protected_names = {
        "server.py", "config.py", "database.py", "models.py", "__init__.py",
    }
    candidates = []
    for path in files:
        p = rel(path)
        if not p.startswith("backend/") or path.suffix != ".py":
            continue
        if "/tests/" in p or path.name.startswith("test_") or path.name in protected_names:
            continue
        full, short = backend_module_name(path)
        if not short:
            continue
        basename = short.split(".")[-1]
        referenced = any(
            item == full or item.startswith(full + ".")
            or item == short or item.startswith(short + ".")
            or item == basename
            for item in imports
        )
        if not referenced:
            candidates.append(p)
    return sorted(candidates)


def duplicate_api_routes(files: list[Path]) -> list[dict]:
    routes: dict[tuple[str, str], list[str]] = defaultdict(list)
    prefix_re = re.compile(r"APIRouter\s*\([^)]*?prefix\s*=\s*[\"']([^\"']*)[\"']", re.S)
    route_re = re.compile(r"@(?:router|app)\.(get|post|put|patch|delete)\s*\(\s*[\"']([^\"']+)[\"']", re.I)
    for path in files:
        p = rel(path)
        if not p.startswith("backend/") or path.suffix != ".py":
            continue
        text = read_text(path)
        prefix_match = prefix_re.search(text)
        prefix = prefix_match.group(1) if prefix_match else ""
        for method, route in route_re.findall(text):
            full_route = (prefix.rstrip("/") + "/" + route.lstrip("/")) if prefix else route
            if not full_route.startswith("/"):
                full_route = "/" + full_route
            routes[(method.upper(), full_route)].append(p)
    result = []
    for (method, route), paths in routes.items():
        unique = sorted(set(paths))
        if len(unique) > 1:
            result.append({"method": method, "route": route, "files": unique})
    return sorted(result, key=lambda x: (x["route"], x["method"]))


def route_stub_duplicate_groups(duplicates: list[dict]) -> list[dict]:
    # Tiny Expo Router wrappers often intentionally share identical content.
    result = []
    for group in duplicates:
        paths = group["paths"]
        if all(p.startswith("frontend/app/") for p in paths) and group["size"] <= 512:
            result.append(group)
    return result


def main() -> int:
    files = git_files()
    duplicates = duplicate_groups(files)
    data = {
        "tracked_files": len(files),
        "generated_or_runtime_candidates": generated_candidates(files),
        "sensitive_filename_candidates": sensitive_filename_candidates(files),
        "duplicate_content_groups": duplicates,
        "intentional_route_stub_duplicate_groups": route_stub_duplicate_groups(duplicates),
        "frontend_potential_orphan_modules": frontend_orphans(files),
        "frontend_unreferenced_asset_candidates": frontend_unreferenced_assets(files),
        "frontend_potential_unused_dependencies": frontend_unused_dependencies(files),
        "backend_potential_orphan_modules": backend_orphans(files),
        "duplicate_api_route_candidates": duplicate_api_routes(files),
    }
    REPORT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")

    lines = [
        "# Repository Hygiene Audit",
        "",
        "> Read-only static scan. Every item below is a candidate until confirmed by build/tests/runtime routing.",
        "",
        f"Tracked files: **{data['tracked_files']}**",
        "",
    ]

    def section(title: str, values, formatter=None):
        lines.extend([f"## {title}", ""])
        if not values:
            lines.extend(["None detected.", ""])
            return
        if formatter:
            for value in values:
                lines.append(formatter(value))
        else:
            for value in values:
                lines.append(f"- `{value}`")
        lines.append("")

    section("Generated / runtime / stale artifact candidates", data["generated_or_runtime_candidates"])
    section("Tracked sensitive-filename candidates", data["sensitive_filename_candidates"])
    section(
        "Potential frontend orphan modules",
        data["frontend_potential_orphan_modules"],
    )
    section("Potential unreferenced frontend assets", data["frontend_unreferenced_asset_candidates"])
    section("Potential unused frontend dependencies", data["frontend_potential_unused_dependencies"])
    section("Potential backend orphan modules", data["backend_potential_orphan_modules"])
    section(
        "Duplicate API route candidates",
        data["duplicate_api_route_candidates"],
        lambda x: f"- `{x['method']} {x['route']}` — " + ", ".join(f"`{p}`" for p in x["files"]),
    )
    section(
        "Duplicate content groups",
        data["duplicate_content_groups"][:100],
        lambda x: f"- **{x['size']} bytes** `{x['sha256'][:12]}` — " + ", ".join(f"`{p}`" for p in x["paths"]),
    )

    lines.extend([
        "## Cleanup rule",
        "",
        "Delete only items that are both statically redundant/unreachable **and** proven safe by the full CI/build/auth-policy gates. Database/customer data is outside this audit.",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(REPORT_MD.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

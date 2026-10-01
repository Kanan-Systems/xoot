"""
Generate src/xoot/THIRD_PARTY_NOTICES.md from the lockfiles, offline.

Which packages: the Python runtime closure of xoot in uv.lock (no dev
group), with environment markers evaluated for CPython on Linux at the
.python-version interpreter, and the npm packages package-lock.json marks as
production, minus those that ship only type declarations and so never reach
the dashboard bundle. What each one is under: the installed dist-info (the
dev environment, env/) and node_modules/. Standard library only.

Usage: python3 scripts/gen_notices.py [--check]
"""

import argparse
import json
import operator
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "src" / "xoot" / "THIRD_PARTY_NOTICES.md"
SITE = REPO / "env" / "lib" / "python3.12" / "site-packages"
NODE_MODULES = REPO / "dashboard" / "node_modules"
_COMPARISON = re.compile(r"^(\w+)\s*(==|!=|<=|>=|<|>)\s*'([^']*)'$")
_OPERATORS = {
    "==": operator.eq, "!=": operator.ne, "<": operator.lt,
    "<=": operator.le, ">": operator.gt, ">=": operator.ge,
}  # fmt: skip
# A holder line, not license prose such as "copyright notice" or a template.
_COPYRIGHT = re.compile(
    r"^\s*(?:(?:Copyright|COPYRIGHT|©)\s+(?!notice|\[yyyy\]|\{yyyy\}|owner|holder)"
    r"|\([cC]\)\s+\d)"
)
_LICENSE_FILE = re.compile(r"^(licen[cs]e|copying|notice)", re.IGNORECASE)
# Trove classifiers for packages whose metadata has no SPDX expression.
_CLASSIFIERS = {
    "MIT License": "MIT",
    "BSD License": "BSD",
    "Apache Software License": "Apache-2.0",
    "ISC License (ISCL)": "ISC",
    "Python Software Foundation License": "PSF-2.0",
}


@dataclass
class Package:
    """One third-party package as the notices list it."""

    name: str
    version: str
    license: str = "UNKNOWN"
    copyright: str = ""
    texts: list[str] = field(default_factory=list)
    # False for an npm package holding only type declarations: never bundled.
    bundled: bool = True


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text))


def marker_holds(marker: str, env: dict[str, str]) -> bool:
    """
    Evaluate the marker forms uv.lock uses: comparisons joined by and/or.

    Args:
        - marker (str): e.g. "sys_platform != 'win32' and python_full_version < '3.13'".
        - env (dict[str, str]): the marker variables of the target environment.

    Returns:
        - holds (bool): whether the dependency applies there.

    Raises:
        - ValueError: a form this evaluator does not know.
    """
    for alternative in marker.split(" or "):
        if all(_compare(part.strip(), env) for part in alternative.split(" and ")):
            return True
    return False


def _compare(part: str, env: dict[str, str]) -> bool:
    match = _COMPARISON.match(part.strip("()"))
    if match is None or match.group(1) not in env:
        raise ValueError(f"unsupported marker: {part!r}")
    name, op, value = match.groups()
    if name.startswith("python"):
        return _OPERATORS[op](_version_tuple(env[name]), _version_tuple(value))
    return _OPERATORS[op](env[name], value)


def python_locked(repo: Path = REPO) -> dict[str, str]:
    """
    The runtime closure of xoot in uv.lock, for the supported environment.

    Args:
        - repo (Path): the checkout.

    Returns:
        - versions (dict[str, str]): normalized name -> version, xoot excluded.
    """
    lock = tomllib.loads((repo / "uv.lock").read_text(encoding="utf-8"))
    python = (repo / ".python-version").read_text(encoding="utf-8").strip()
    env = {
        "sys_platform": "linux",
        "platform_system": "Linux",
        "platform_python_implementation": "CPython",
        "implementation_name": "cpython",
        "python_full_version": python,
        "python_version": ".".join(python.split(".")[:2]),
    }
    packages = {entry["name"]: entry for entry in lock["package"]}
    found: dict[str, str] = {}
    pending: list[tuple[str, tuple[str, ...]]] = [("xoot", ())]
    while pending:
        name, extras = pending.pop()
        entry = packages[name]
        optional = entry.get("optional-dependencies", {})
        wanted = entry.get("dependencies", []) + [
            dep for extra in extras for dep in optional.get(extra, [])
        ]
        for dependency in wanted:
            marker = dependency.get("marker")
            if marker and not marker_holds(marker, env):
                continue
            # A package already seen is walked again only for a new extra.
            child, more = dependency["name"], tuple(dependency.get("extra", []))
            if child in found and not more:
                continue
            found[child] = packages[child]["version"]
            pending.append((child, more))
    return found


def npm_locked(repo: Path = REPO) -> dict[str, str]:
    """
    Every package package-lock.json marks as production, from the lockfile
    alone (the notices then say which of them hold only type declarations).

    Args:
        - repo (Path): the checkout.

    Returns:
        - versions (dict[str, str]): package name -> version.
    """
    lock = json.loads((repo / "dashboard" / "package-lock.json").read_text("utf-8"))
    found: dict[str, str] = {}
    for path, entry in lock["packages"].items():
        if not path or entry.get("dev"):
            continue
        found[path.rsplit("node_modules/", 1)[1]] = entry["version"]
    return found


def _copyright(texts: list[str]) -> str:
    for text in texts:
        for line in text.splitlines():
            if _COPYRIGHT.match(line):
                return " ".join(line.split())
    return ""


def python_package(name: str, version: str, site: Path) -> Package:
    """Read one installed distribution's license metadata and files."""
    stem = re.sub(r"[-_.]+", "_", name)
    info = site / f"{stem}-{version}.dist-info"
    metadata = (info / "METADATA").read_text(encoding="utf-8")
    headers = [
        line.split(": ", 1) for line in metadata.split("\n\n", 1)[0].splitlines()
    ]
    values = [(key, value) for key, value, *_ in (h + [""] for h in headers)]
    package = Package(name, version)
    expression = [v for k, v in values if k == "License-Expression"]
    classifiers = [
        _CLASSIFIERS.get(v.rsplit(" :: ", 1)[-1], "")
        for k, v in values
        if k == "Classifier" and v.startswith("License ::")
    ]
    plain = [v for k, v in values if k == "License" and v and len(v) < 60]
    package.license = next(
        iter(expression + [c for c in classifiers if c] + plain), "UNKNOWN"
    )
    for key, value in values:
        if key == "License-File":
            for candidate in (info / "licenses" / value, info / value):
                if candidate.is_file():
                    package.texts.append(candidate.read_text(encoding="utf-8"))
                    break
    package.copyright = _copyright(package.texts)
    return package


def npm_package(name: str, version: str, modules: Path) -> Package:
    """Read one installed npm package's license field and files."""
    root = modules / name
    manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
    package = Package(name, version, str(manifest.get("license", "UNKNOWN")))
    # No entry point and no index.js (Node's default): only type declarations.
    entry = any(manifest.get(key) for key in ("main", "module", "exports"))
    runtime = entry or (root / "index.js").is_file()
    package.bundled = runtime and not name.startswith("@types/")
    for path in sorted(root.iterdir()):
        if path.is_file() and _LICENSE_FILE.match(path.name):
            package.texts.append(path.read_text(encoding="utf-8"))
    package.copyright = _copyright(package.texts)
    return package


def _table(packages: list[Package]) -> list[str]:
    lines = ["| Package | Version | License | Copyright |", "|---|---|---|---|"]
    for p in packages:
        holder = (p.copyright or "no copyright line in its license file").replace(
            "|", "\\|"
        )
        lines.append(f"| {p.name} | {p.version} | {p.license} | {holder} |")
    return lines


def render(python: list[Package], npm: list[Package]) -> str:
    """
    Build the notices document.

    Args:
        - python (list[Package]): the Python packages, sorted.
        - npm (list[Package]): the npm packages, sorted.

    Returns:
        - text (str): the Markdown file.
    """
    out = [
        "# Third-party notices",
        "",
        "xoot ships or runs the packages below. This file is generated by",
        "`scripts/gen_notices.py` from `uv.lock`, `dashboard/package-lock.json`",
        "and the license files of the installed packages; do not edit it by hand.",
        "",
        "## Python packages (runtime dependencies, Linux, CPython)",
        "",
        *_table(python),
        "",
        "## JavaScript packages bundled into the dashboard",
        "",
        *_table([p for p in npm if p.bundled]),
        "",
        "Production dependencies that hold only TypeScript declarations never",
        "reach the bundle and are not listed above: "
        + ", ".join(f"{p.name} {p.version}" for p in npm if not p.bundled)
        + ".",
        "",
        "## Packages without a license file",
        "",
    ]
    bare = [p for p in python + npm if p.bundled and not p.texts]
    out += [
        f"- {p.name} {p.version}: no license file is shipped; its metadata "
        f"names the license as {p.license}."
        for p in bare
    ] or ["Every listed package ships its license file."]
    groups: dict[str, list[Package]] = {}
    for p in python + [p for p in npm if p.bundled]:
        for text in p.texts:
            groups.setdefault(text.strip(), []).append(p)
    out += ["", "## License texts"]
    for number, (text, users) in enumerate(groups.items(), start=1):
        names = ", ".join(f"{p.name} {p.version}" for p in users)
        out += ["", f"### License text {number}", "", f"Used by: {names}.", ""]
        out += ["````text", text, "````"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the notices, or with --check report whether they are current."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--check", action="store_true", help="fail if stale")
    args = parser.parse_args(argv)
    python = [python_package(n, v, SITE) for n, v in sorted(python_locked().items())]
    npm = [npm_package(n, v, NODE_MODULES) for n, v in sorted(npm_locked().items())]
    text = render(python, npm)
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != text:
            print(f"{OUTPUT} is stale; run scripts/gen_notices.py", file=sys.stderr)
            return 1
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT}: {len(python)} Python and {len(npm)} npm packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure complete Python/shell source scope without crediting modified copies."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

INVENTORY = "inventory.json"
COVERAGE_CONFIG = "coverage.rc"
COVERAGE_DATA = ".coverage"
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
HELPERS = HERE / "sonar_coverage"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_sources(root, manifest):
    for item in manifest["files"]:
        path = root / item["path"]
        if digest(path) != item["sha256"]:
            raise ValueError("coverage source changed: " + item["path"])


def stage_shell_sources(root, out, manifest):
    sources = out / "shell-sources"
    sources.mkdir()
    hashes = []
    for item in manifest["files"]:
        if item["language"] != "shell" or item["test"]:
            continue
        target = sources / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / item["path"], target)
        hashes.append(item["sha256"])
    return sources, hashes


def shell_baseline(out, sources, kcov):
    launcher = out / "parse-shell.sh"
    launcher.write_text("#!/usr/bin/env bash\n:\n", encoding="utf-8")
    subprocess.run([
        str(kcov), "--bash-dont-parse-binary-dir",
        "--bash-parse-files-in-dir=" + str(sources),
        "--include-path=" + str(sources), "--output-interval=0",
        str(out / "shell-baseline"), str(launcher)], check=True)
    # kcov's report writer may outlive its launcher. Accept only a complete
    # XML document; an absent/truncated report is never an empty denominator.
    deadline = time.monotonic() + 15
    while True:
        reports = sorted({path.resolve() for path in (out / "shell-baseline").glob("*/sonarqube.xml")
                          if path.parent.name != "kcov-merged"})
        try:
            if len(reports) != 1:
                raise ValueError("expected exactly one kcov shell denominator report")
            ET.parse(reports[0])
            break
        except (ValueError, ET.ParseError, OSError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)
    shutil.copyfile(reports[0], out / "shell-baseline.xml")


def coverage_environment(root, out, hashes):
    config = out / COVERAGE_CONFIG
    config.write_text(
        "[run]\ncore = ctrace\nparallel = true\nsigterm = false\nplugins = provenance\n"
        "data_file = " + str(out / COVERAGE_DATA) + "\n"
        "omit =\n    */site-packages/*\n    /usr/*\n"
        "disable_warnings = no-data-collected, module-not-measured\n",
        encoding="utf-8")
    env = {
        "ORT_SONAR_ROOT": str(root), "ORT_SONAR_INVENTORY": str(out / INVENTORY),
        "COVERAGE_PROCESS_START": str(config), "COVERAGE_CORE": "ctrace",
        "PYTHONPATH": str(HELPERS) + (os.pathsep + os.environ["PYTHONPATH"]
                                    if os.environ.get("PYTHONPATH") else ""),
        "BASH_ENV": str(HELPERS / "bash-env.sh"),
        "ORT_SONAR_SHELL_HASHES": ":".join(sorted(set(hashes))),
        "ORT_SONAR_SHELL_HITS": str(out / "shell-hits"),
    }
    (out / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as stream:
            for key, value in env.items():
                if key == "BASH_ENV":
                    continue  # GitHub forbids setting BASH_ENV through GITHUB_ENV
                if "\n" in value or "\r" in value:
                    raise ValueError("multiline coverage environment")
                stream.write(key + "=" + value + "\n")
    return env




def probe_python_copy_attribution(root, out, manifest, env):
    """Refuse an engine that silently drops the provenance file-tracer plug-in."""
    import sys
    from coverage import Coverage

    sys.path.insert(0, str(HELPERS))
    os.environ["ORT_SONAR_ROOT"] = str(root)
    os.environ["ORT_SONAR_INVENTORY"] = str(out / INVENTORY)
    source = (root / "code/lanes-index").read_bytes()
    # T124 (tasks:2850; FR-064): `lanes-index` is a launcher that runs its
    # body from `lanes_index_main.py` beside it, so each copy has the module.
    module = (root / "code/lanes_index_main.py").read_bytes()
    checksum = hashlib.sha256(source).hexdigest()
    canonical = next(root / item["path"] for item in manifest["files"]
                     if item["language"] == "py" and not item["test"]
                     and item["sha256"] == checksum)
    module_canonical = next(root / item["path"] for item in manifest["files"]
                            if item["language"] == "py" and not item["test"]
                            and item["sha256"] == hashlib.sha256(module).hexdigest())
    results, module_results = {}, {}
    # "module-modified" runs an exact launcher with a changed module from the
    # checkout's own directory, where the exact module is: the module's code
    # carries the bare name `lanes_index_main.py`, and its credit follows the
    # module that ran, never the one the working directory holds.
    for kind in ("exact", "modified", "module-modified"):
        directory = out / "provenance-probe" / kind
        directory.mkdir(parents=True)
        command = directory / "copied-python-command"
        command.write_bytes(source + b"\n# changed copy\n" if kind == "modified" else source)
        (directory / "lanes_index_main.py").write_bytes(
            module + b"\n# changed copy\n" if kind == "module-modified" else module)
        config = directory / COVERAGE_CONFIG
        settings = (out / COVERAGE_CONFIG).read_text()
        config.write_text(settings.replace(str(out / COVERAGE_DATA), str(directory / COVERAGE_DATA)))
        child_env = {**os.environ, **env, "COVERAGE_PROCESS_START": str(config),
                     "COVERAGE_FILE": str(directory / COVERAGE_DATA)}
        result = subprocess.run([sys.executable, str(command), "--help"],
                                cwd=root / "code" if kind == "module-modified" else directory,
                                env=child_env, capture_output=True, text=True, timeout=30,
                                check=True)
        if result.stderr:
            raise RuntimeError("coverage provenance probe emitted diagnostics: " + result.stderr)
        measured = Coverage(config_file=str(config), data_file=str(directory / COVERAGE_DATA))
        measured.combine(data_paths=[str(directory)], strict=True, keep=True)
        data = measured.get_data()
        module_results[kind] = len(data.lines(str(module_canonical)) or [])
        if kind != "module-modified":
            results[kind] = len(data.lines(str(canonical)) or [])
    if results["exact"] <= 0 or results["modified"] != 0:
        raise RuntimeError("Python source-copy attribution failed: " + json.dumps(results))
    if module_results["exact"] <= 0 or module_results["module-modified"] != 0:
        raise RuntimeError("Python module attribution failed: " + json.dumps(module_results))
    # Diagnostic probe data stays in its own nested directories; it is never
    # combined into the suite's coverage or credited toward the quality gate.
    (out / "provenance-probe.json").write_text(json.dumps(results, indent=2) + "\n")
    print("Python copy attribution:", json.dumps(results))


def prepare(root, out, kcov):
    import coverage
    print("measurement tool: coverage.py", coverage.__version__)
    try:
        tracer = importlib.import_module("coverage.tracer")
    except ImportError as exc:
        raise RuntimeError("source-copy attribution requires coverage's C tracer") from exc
    if not getattr(tracer, "CTracer", None):
        raise RuntimeError("source-copy attribution requires coverage's C tracer")
    root, out = root.resolve(), out.resolve()
    manifest = json.loads((out / INVENTORY).read_text())
    checked_sources(root, manifest)
    sources, hashes = stage_shell_sources(root, out, manifest)
    shell_baseline(out, sources, kcov)
    env = coverage_environment(root, out, hashes)
    probe_python_copy_attribution(root, out, manifest, env)
    return env


def shell_denominators(out, by_path):
    result = {}
    sources = (out / "shell-sources").resolve()
    for element in ET.parse(out / "shell-baseline.xml").getroot().findall("file"):
        path = Path(element.attrib["path"]).resolve()
        relative = path.relative_to(sources).as_posix()
        if relative not in by_path:
            raise ValueError("unknown shell denominator source: " + relative)
        if digest(path) != by_path[relative]["sha256"]:
            raise ValueError("shell denominator bytes changed: " + relative)
        result[relative] = {
            int(line.attrib["lineNumber"]): False
            for line in element.findall("lineToCover")}
    absent = [name for name in by_path if not result.get(name)]
    if absent:
        raise ValueError("kcov omitted shell source denominators: " + ", ".join(absent))
    return result


def apply_shell_hits(out, by_hash, result):
    path = out / "shell-hits"
    if not path.exists():
        return
    for row in path.read_text().splitlines():
        checksum, value = row.split("\t")
        if checksum not in by_hash:
            raise ValueError("unknown shell hit source")
        number = int(value)
        for item in by_hash[checksum]:
            if not 1 <= number <= item["lines"]:
                raise ValueError("shell hit outside source: " + item["path"])
            # DEBUG also emits events for closing constructs. Only the fixed
            # executable baseline is coverable; observations cannot enlarge it.
            if number in result[item["path"]]:
                result[item["path"]][number] = True


def shell_lines(out, manifest):
    by_path = {item["path"]: item for item in manifest["files"]
               if item["language"] == "shell" and not item["test"]}
    by_hash = {}
    for item in by_path.values():
        by_hash.setdefault(item["sha256"], []).append(item)
    result = shell_denominators(out, by_path)
    apply_shell_hits(out, by_hash, result)
    return result


def python_lines(root, out, manifest):
    import sys
    sys.path.insert(0, str(HELPERS))
    os.environ["ORT_SONAR_ROOT"] = str(root)
    os.environ["ORT_SONAR_INVENTORY"] = str(out / INVENTORY)
    from coverage import Coverage
    from coverage.parser import PythonParser

    cov = Coverage(config_file=str(out / COVERAGE_CONFIG))
    cov.combine(data_paths=[str(out)], strict=True)
    cov.save()
    data = cov.get_data()
    by_hash = {}
    for item in manifest["files"]:
        if item["language"] == "py" and not item["test"]:
            by_hash.setdefault(item["sha256"], set()).update(
                data.lines(str(root / item["path"])) or [])
    result = {}
    for item in manifest["files"]:
        if item["language"] != "py" or item["test"]:
            continue
        parser = PythonParser(filename=str(root / item["path"]))
        parser.parse_source()
        hits = by_hash[item["sha256"]]
        if any(not 1 <= number <= item["lines"] for number in hits):
            raise ValueError("Python hit outside source: " + item["path"])
        # Raw tracing includes docstrings and continuation/closing lines.
        # Use Coverage's canonical statement mapping, retaining every missing
        # statement without adding observed-only lines to the denominator.
        executed = parser.translate_lines(hits)
        result[item["path"]] = {
            number: number in executed for number in parser.statements}
    return result


def write_report(out, manifest, measurements):
    expected = {item["path"] for item in manifest["files"] if not item["test"]}
    if set(measurements) != expected:
        raise ValueError("coverage source inventory is incomplete")
    xml = ET.Element("coverage", version="1")
    summary = {"files": len(expected), "languages": {}}
    for item in manifest["files"]:
        if item["test"]:
            continue
        lines = measurements[item["path"]]
        if any(not 1 <= number <= item["lines"] for number in lines):
            raise ValueError("coverage line outside source: " + item["path"])
        element = ET.SubElement(xml, "file", path=item["path"])
        for number, covered in sorted(lines.items()):
            ET.SubElement(element, "lineToCover", lineNumber=str(number),
                          covered="true" if covered else "false")
        total = summary["languages"].setdefault(item["language"],
                                                {"covered": 0, "lines": 0})
        total["covered"] += sum(lines.values())
        total["lines"] += len(lines)
    for lang, total in summary["languages"].items():
        if not total["covered"] or not total["lines"]:
            raise ValueError("no measured " + lang + " coverage")
    ET.indent(xml)
    ET.ElementTree(xml).write(out / "coverage.xml", encoding="utf-8",
                              xml_declaration=True)
    (out / "coverage-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    from sonar_assurance import ci_paths

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "report"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, out = ci_paths(args.root, args.out)
    if args.command == "prepare":
        prepare(root, out, Path(os.environ["RUNNER_TEMP"]) / "kcov-build/src/kcov")
    else:
        manifest = json.loads((out / INVENTORY).read_text())
        checked_sources(root, manifest)
        measurements = python_lines(root, out, manifest)
        measurements.update(shell_lines(out, manifest))
        write_report(out, manifest, measurements)


if __name__ == "__main__":
    main()

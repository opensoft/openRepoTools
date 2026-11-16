# SPDX-License-Identifier: Apache-2.0
"""Claim Python files only after hashing their bytes, including fixture copies."""
import hashlib
import json
import os
from pathlib import Path

from coverage import CoveragePlugin, FileTracer

#: T124 (tasks:2850; FR-064): `lanes-index` runs its body from this module's
#: code, compiled under this bare name, which `ready`'s check 1 and the install
#: give it too. Coverage resolves a bare name against the working directory,
#: then `sys.path`, so the file it names need not be the one that ran. The
#: launcher reads the module beside the `realpath` of its own `__file__`, which
#: the module's code shares, so each frame's module is found there and hashed.
MODULE = "lanes_index_main.py"


class Source(FileTracer):
    def __init__(self, filename):
        self.filename = filename

    def source_filename(self):
        return self.filename


class Module(FileTracer):
    def __init__(self, plugin):
        self.plugin = plugin
        self.seen = {}

    def has_dynamic_source_filename(self):
        return True

    def dynamic_source_filename(self, filename, frame):
        key = (frame.f_code.co_filename, frame.f_globals.get("__file__"))
        if key not in self.seen:
            name, launcher = key
            if not os.path.isabs(name):
                name = (os.path.join(os.path.dirname(os.path.realpath(launcher)), name)
                        if launcher else None)
            self.seen[key] = self.plugin.canonical(name) if name else None
        return self.seen[key]


class Provenance(CoveragePlugin):
    def __init__(self, options):
        root = Path(os.environ["ORT_SONAR_ROOT"]).resolve()
        manifest = json.loads(Path(os.environ["ORT_SONAR_INVENTORY"]).read_text())
        self.sources = {}
        for item in manifest["files"]:
            if item["language"] == "py" and not item["test"]:
                self.sources.setdefault(item["sha256"], str(root / item["path"]))

    def canonical(self, filename):
        try:
            digest = hashlib.sha256(Path(filename).read_bytes()).hexdigest()
        except OSError:
            return None
        return self.sources.get(digest)

    def file_tracer(self, filename):
        if os.path.basename(filename) == MODULE:
            return Module(self)
        canonical = self.canonical(filename)
        return Source(canonical) if canonical else None

    def file_reporter(self, filename):
        return "python"


def coverage_init(registry, options):
    registry.add_file_tracer(Provenance(options))

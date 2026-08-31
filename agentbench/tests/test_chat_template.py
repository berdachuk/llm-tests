"""Chat-template installation sanity checks.

These are local/offline checks (no network call to the server) that reuse
`check_applied.py` (from froggeric/Qwen-Fixed-Chat-Templates/scripts) to
confirm the expected template version string is present in a given
chat_template.jinja file. Point them at a local copy of the model's template
via `--template-path` / `AGENTBENCH_TEMPLATE_PATH`; skipped if not provided,
since the canonical copy lives on the remote server
(/mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8/chat_template.jinja) and
this suite otherwise only talks to the server's HTTP API, not its
filesystem.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

REPRO_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPRO_DIR))
import check_applied  # noqa: E402


@pytest.fixture(scope="module")
def template_path() -> Path:
    p = os.environ.get("AGENTBENCH_TEMPLATE_PATH")
    if not p:
        pytest.skip(
            "set AGENTBENCH_TEMPLATE_PATH to a local chat_template.jinja (or model dir) "
            "to run chat-template installation checks"
        )
    path = Path(p)
    if not path.exists():
        pytest.skip(f"AGENTBENCH_TEMPLATE_PATH does not exist: {path}")
    return path


def test_template_version_is_froggeric(template_path: Path):
    jinja_file = template_path / "chat_template.jinja" if template_path.is_dir() else template_path
    assert jinja_file.exists(), f"no chat_template.jinja found at {jinja_file}"
    content = jinja_file.read_text(encoding="utf-8")
    version = check_applied.extract_template_version(content)
    assert "froggeric" in version, f"expected froggeric-patched template, found: {version!r}"


def test_template_version_is_recent_v22(template_path: Path):
    jinja_file = template_path / "chat_template.jinja" if template_path.is_dir() else template_path
    content = jinja_file.read_text(encoding="utf-8")
    version = check_applied.extract_template_version(content)
    m = re.search(r"v(\d+)(?:\.(\d+))?", version)
    assert m, f"could not parse a version number out of {version!r}"
    major = int(m.group(1))
    assert major >= 22, f"expected froggeric v22+, found {version!r}"


def test_original_template_was_backed_up(template_path: Path):
    """Regression guard for the install step performed on the server: the
    original vendor chat_template.jinja must be preserved as
    chat_template.jinja.orig, not silently discarded, so it can be restored
    if the froggeric template ever needs to be rolled back."""
    if not template_path.is_dir():
        pytest.skip("only meaningful when pointed at a model directory")
    backup = template_path / "chat_template.jinja.orig"
    assert backup.exists(), f"expected a backup of the original template at {backup}"
    original_content = backup.read_text(encoding="utf-8")
    original_version = check_applied.extract_template_version(original_content)
    assert "froggeric" not in original_version, (
        "chat_template.jinja.orig should be the *original* vendor template, "
        f"but it already reports a froggeric version ({original_version!r})"
    )

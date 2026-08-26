#!/usr/bin/env python3
"""Render the canonical reviewer policy into per-harness adapters.

One policy, many harnesses. Each harness wants the same text in a different
wrapper — TOML developer instructions for Codex, YAML frontmatter for a Claude
subagent — and every wrapper records the sha256 of the policy it came from, so
`--check` can tell you when an adapter has drifted from the source.

Never hand-edit a generated adapter. Edit reviewers/tech-lead-reviewer.md and
re-run this.

The second review path is optional. When TECH_LEAD_SECOND_ENABLED is not true,
no Claude subagent is emitted and the dispatch instructions say nothing about a
second reviewer — so a project that cannot run one is never told to.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

# Read from the tool.
POLICY_PATH: Final = Path("reviewers/tech-lead-reviewer.md")

# Written into the project. Everything generated lands under .tech-lead/ except the
# harness subagent, which has to sit where the harness looks for it.
OUTPUT_DIR: Final = Path(".tech-lead")
SUBAGENT_PATH: Final = Path(".claude/agents/tech-lead-reviewer.md")

TRUE_VALUES: Final = {"1", "true", "yes", "on"}


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in TRUE_VALUES


def project_root(tool_root: Path) -> Path:
    """The repository being reviewed, which is not always where this tool lives.

    Vendored as a submodule, the tool sits inside somebody else's repository, and
    everything it writes belongs to that repository rather than to itself.
    """
    override = os.environ.get("TECH_LEAD_PROJECT_ROOT", "").strip()
    if override:
        return Path(override).resolve()
    for args in (
        ["git", "rev-parse", "--show-superproject-working-tree"],
        ["git", "rev-parse", "--show-toplevel"],
    ):
        try:
            found = subprocess.run(
                args, capture_output=True, text=True, check=False
            ).stdout.strip()
        except OSError:
            found = ""
        if found:
            return Path(found).resolve()
    return tool_root


def load_env(root: Path) -> None:
    """Read .env if present. Values already in the environment win."""
    env_file = root / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def render(policy_bytes: bytes, *, second_enabled: bool, second_model: str,
           second_effort: str) -> dict[Path, bytes]:
    digest = hashlib.sha256(policy_bytes).hexdigest()
    policy = policy_bytes.decode("utf-8")
    stamp = f"Generated from {POLICY_PATH}; canonical-sha256: {digest}"

    out: dict[Path, bytes] = {}

    out[OUTPUT_DIR / "codex-tech-lead.toml"] = "\n".join(
        [
            f"# {stamp}",
            'name = "tech_lead_reviewer"',
            'description = "Read-only reviewer for load-bearing designs and plans."',
            'sandbox_mode = "read-only"',
            f"developer_instructions = {json.dumps(policy)}",
            "",
        ]
    ).encode()

    out[OUTPUT_DIR / "claude-tech-lead.md"] = "\n".join(
        [
            "---",
            "name: tech-lead-reviewer",
            "description: Read-only reviewer for load-bearing designs and plans.",
            "tools: Read, WebFetch, WebSearch",
            "---",
            f"<!-- {stamp} -->",
            "",
            policy.rstrip("\n"),
            "",
        ]
    ).encode()

    out[OUTPUT_DIR / "hermes-tech-lead.md"] = "\n".join(
        [
            f"<!-- {stamp} -->",
            "# Hermes Tech Lead Invocation",
            "",
            "Select the reviewer model and provider at dispatch time. Supply the",
            "gate, artifact revision, and canonical policy to `delegate_task`.",
            "Disable terminal and write capabilities for the child when the installed",
            "Hermes version supports it; otherwise disclose behavioral-only read-only",
            "guidance in the review metadata.",
            "",
            policy.rstrip("\n"),
            "",
        ]
    ).encode()

    if second_enabled:
        # Pins the second path's identity. Hand-maintained equivalents drift; this
        # one is regenerated whenever the policy or the configured model changes.
        out[SUBAGENT_PATH] = "\n".join(
            [
                "---",
                "name: tech-lead-reviewer",
                "description: >-",
                "  Read-only Tech Lead reviewer, second path. Dispatched at gates 3",
                "  and 4 alongside the primary path, for a same-artifact comparison",
                "  between providers.",
                f"model: {second_model}",
                f"effort: {second_effort}",
                "tools: Read, Bash",
                "---",
                f"<!-- {stamp} -->",
                "",
                "# Tech Lead Reviewer — second path",
                "",
                "Before doing anything else, read `.tech-lead/claude-tech-lead.md`",
                "and apply it in full as your policy. It is generated from the",
                "canonical policy, and `generate-adapters.py --check` fails if the two",
                "disagree. If that file is missing, stop and report it rather than",
                "reviewing from memory of what the policy usually says.",
                "",
                "The dispatch supplies the gate, the artifact path, and the",
                "artifact's revision or SHA-256. Report the metadata block the policy",
                "requires. For read-only enforcement state `tool restriction` — this",
                "subagent's `tools` allowlist is what holds you read-only, not an OS",
                "sandbox.",
                "",
                "You run at gates 3 and 4 only, on the same artifact and revision the",
                "primary path receives. **Do not read the primary path's review",
                "before producing your own.** The comparison is worthless if the two",
                "are not independent.",
                "",
            ]
        ).encode()

    out[OUTPUT_DIR / "dispatch-instructions.md"] = dispatch_text(
        stamp, second_enabled=second_enabled
    ).encode()
    return out


def dispatch_text(stamp: str, *, second_enabled: bool) -> str:
    lines = [
        f"<!-- {stamp} -->",
        "# Tech Lead Review",
        "",
        "Paste this section into the consuming project's `AGENTS.md`.",
        "",
        "---",
        "",
        "## Tech Lead Review",
        "",
        "Load-bearing design and planning work passes four gates:",
        "",
        "1. **Approach selected** — before presenting the first design section.",
        "2. **Design section locked** — before moving to the next section. Applies",
        "   only to a load-bearing section, not routine documentation or scaffolding.",
        "3. **Specification finalized** — before asking the user to review it.",
        "4. **Implementation plan finalized** — before implementing.",
        "",
        "Run a gate with:",
        "",
        "```",
        "./bin/review-gate.sh <gate> <artifact-path> [prior-findings-file]",
        "```",
        "",
        "### The user authorizes every round",
        "",
        "**Propose a gate review; do not run one unprompted, and never re-dispatch",
        "on your own judgement.** After each review, present every Critical and",
        "Important finding to the user unaltered, say what you propose to do about",
        "each, and let the user decide what gets fixed and whether another round",
        "runs at all.",
        "",
        "This is deliberate. An automatic fix-and-re-review loop runs until the",
        "reviewer runs out of objections, which is not the same as the artifact",
        "being right — it manufactures findings about work nobody has done yet and",
        "spends the reviewer's rigor on prose rather than on something checkable",
        "against reality.",
        "",
        "You may fix a finding, justify it with evidence in the artifact, or route",
        "it onward unaltered. You may not downgrade, merge, or withhold one, and you",
        "report what you did to each.",
        "",
        "Reviews are written to `.review-log/` so a re-review can be given the prior",
        "findings, and so a review survives a restart.",
        "",
    ]
    if second_enabled:
        lines += [
            "### Second path (enabled)",
            "",
            "At gates 3 and 4, also dispatch the `tech-lead-reviewer` subagent on the",
            "same artifact and revision. Run the two independently and **do not show",
            "either reviewer the other's findings** — the paths exist to be compared,",
            "and the comparison is worthless if they anchor on each other.",
            "",
            "Treat both outputs as the gate review. When the two disagree on a",
            "finding's severity, take the higher: a defect must not pass on the more",
            "lenient of two opinions, and the cost of being wrong is one unnecessary",
            "fix.",
            "",
            "After the second path returns, write its review to `.review-log/` as",
            "`gate<N>-<path>-<artifact-slug>-<timestamp>.md`, matching the script's",
            "scheme and taking the timestamp from the review's own metadata block.",
            "",
        ]
    else:
        lines += [
            "### Second path (disabled)",
            "",
            "This project runs a single reviewer. To add a second opinion at gates 3",
            "and 4, set `TECH_LEAD_SECOND_ENABLED=true` in `.env` and re-run",
            "`bin/generate-adapters.py`.",
            "",
        ]
    lines += [
        "### Runtime identity",
        "",
        "The reviewer's provider, model, and effort come from `.env` and nowhere",
        "else. Never pin a model in a generated adapter, and never vary the identity",
        "between gates or passes. Record both the requested and the effective",
        "identity with each review — they can differ.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="the tool directory (where reviewers/ lives)",
    )
    parser.add_argument(
        "--check", action="store_true", help="fail on drift instead of writing"
    )
    args = parser.parse_args(argv)
    tool_root: Path = args.root.resolve()
    root = project_root(tool_root)

    load_env(root)
    second_enabled = env_flag("TECH_LEAD_SECOND_ENABLED")
    second_model = os.environ.get("TECH_LEAD_SECOND_MODEL", "").strip()
    second_effort = os.environ.get("TECH_LEAD_SECOND_EFFORT", "").strip()

    if second_enabled and not second_model:
        print(
            "TECH_LEAD_SECOND_ENABLED is true but TECH_LEAD_SECOND_MODEL is unset",
            file=sys.stderr,
        )
        return 1

    policy_path = tool_root / POLICY_PATH
    if not policy_path.is_file():
        print(f"missing canonical policy: {policy_path}", file=sys.stderr)
        return 1

    expected = render(
        policy_path.read_bytes(),
        second_enabled=second_enabled,
        second_model=second_model,
        second_effort=second_effort or "max",
    )

    drifted: list[Path] = []
    for relative, content in expected.items():
        target = root / relative
        if args.check:
            if not target.is_file() or target.read_bytes() != content:
                drifted.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    # A disabled second path must not leave a stale subagent behind, or a project
    # that turned it off would still be told to dispatch a reviewer it cannot run.
    stale = root / SUBAGENT_PATH
    if not second_enabled and stale.is_file():
        if args.check:
            drifted.append(stale.relative_to(root))
        else:
            stale.unlink()

    if drifted:
        for path in drifted:
            print(f"adapter drift: {path}", file=sys.stderr)
        print("run bin/generate-adapters.py to regenerate", file=sys.stderr)
        return 1

    if not args.check:
        state = (
            f"enabled ({second_model}/{second_effort or 'max'})"
            if second_enabled
            else "disabled"
        )
        print(f"wrote {len(expected)} files into {root}; second path {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

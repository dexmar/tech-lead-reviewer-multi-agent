# tech-lead-reviewer-multi-agent

An independent, read-only technical reviewer for design and planning work, dispatched
at four gates and run on whichever model you choose — including one that isn't the
model doing the work.

The point is not more review. It's review by something that did not write the thing,
does not share its assumptions, and has to cite evidence for every objection.

## Why a different model

An author is the worst reviewer of their own hand-waving. Running the reviewer on a
different provider gets you an opinion that never saw the design conversation and has
no stake in the choices — and, incidentally, draws on a separate usage pool, so
reviews stop consuming the budget you're using to build.

Optionally you can run **two** reviewers at gates 3 and 4 and compare. In practice
they disagree usefully: in one session the two paths overlapped on four findings and
found five and one respectively that the other missed entirely.

## The four gates

| Gate | When | Catches |
|---|---|---|
| 1 | Approach selected, before the first design section | Preference dressed up as reasoning; alternatives dismissed without substance; unneeded infrastructure |
| 2 | A load-bearing design section is locked | Hedging where a decision is owed; unevidenced cost and risk claims; YAGNI |
| 3 | Specification finalized | Cross-section contradiction; requirements that aren't implementable; untestable error handling |
| 4 | Implementation plan finalized | File-path and line-number drift; identifiers that disagree between tasks; phase ordering; verification gaps |

Gate 4 deliberately does not re-open gates 1–3. If the spec says X, the plan must
implement X; believing X is wrong is a gate 3 finding that should have surfaced
earlier.

## The user authorizes every round

**The agent proposes a review. It does not run one unprompted, and it never
re-dispatches on its own judgement.** After each review it presents every Critical and
Important finding unaltered, says what it proposes to do about each, and the human
decides what gets fixed and whether another round happens at all.

This is the single most important thing in this repo, and it was learned the hard way.
An automatic fix-and-re-review loop runs until the reviewer runs out of objections,
which is not the same as the artifact being right. Left to itself it starts
manufacturing findings about work nobody has done yet, and spends real reasoning on
prose instead of on something that can be checked against reality.

The corollary: review is most valuable when there's something concrete to check a
claim against. Reviewing a spec that describes unwritten code produces opinions.
Reviewing a spec whose claims can be tested against real data produces bugs.

## Install

Vendor it as a submodule, from your project's root:

```sh
git submodule add https://github.com/dexmar/tech-lead-reviewer-multi-agent \
    tools/tech-lead-reviewer
cp tools/tech-lead-reviewer/.env.example .env    # then edit
python3 tools/tech-lead-reviewer/bin/generate-adapters.py
```

That writes into **your** repository, not into the submodule:

```
.tech-lead/codex-tech-lead.toml       generated adapters
.tech-lead/claude-tech-lead.md
.tech-lead/hermes-tech-lead.md
.tech-lead/dispatch-instructions.md   paste into your AGENTS.md
.claude/agents/tech-lead-reviewer.md  only when the second path is enabled
```

The tool distinguishes where it lives from the repository it is reviewing. Policy
and templates are read from the submodule; `.env`, domain checks, artifacts,
generated output and `.review-log/` all belong to your project. It finds your root
with `git rev-parse`, handling the submodule case, and `TECH_LEAD_PROJECT_ROOT`
overrides it.

Paste `.tech-lead/dispatch-instructions.md` into your `AGENTS.md` (or `CLAUDE.md`,
or whatever your harness reads). It is generated to match your configuration — with
the second path off, it says nothing about a second reviewer.

Requirements: `bash`, `python3`, `git`, and the [Codex
CLI](https://github.com/openai/codex) on `PATH` for the primary path.

### Pushing changes back

Because it is a submodule, improvements travel:

```sh
cd tools/tech-lead-reviewer
# edit reviewers/tech-lead-reviewer.md
git commit -am "..." && git push
cd ../.. && git add tools/tech-lead-reviewer && git commit -m "bump reviewer"
```

Two commits, and that separation is the point: a policy change cannot ride along
inside a project commit.

## Configure

Everything lives in `.env`. Nothing else may pin a model — not an adapter, not a
subagent file, not a dispatcher.

```sh
TECH_LEAD_PROVIDER=codex
TECH_LEAD_MODEL=gpt-5.6-sol
TECH_LEAD_EFFORT=max

# Optional second opinion at gates 3 and 4. Off by default.
TECH_LEAD_SECOND_ENABLED=false
TECH_LEAD_SECOND_MODEL=fable
TECH_LEAD_SECOND_EFFORT=max
```

The second path is opt-in on purpose: it costs a second review and needs a model your
plan includes. With it off, no subagent adapter is generated and the dispatch
instructions never mention a reviewer you can't run.

## Run a gate

```sh
./tools/tech-lead-reviewer/bin/review-gate.sh 3 docs/specs/my-design.md
./tools/tech-lead-reviewer/bin/review-gate.sh 3 docs/specs/my-design.md \
    .review-log/gate3-codex-....md
```

The third argument passes the prior review back, so a re-review checks whether its own
findings were addressed rather than re-deriving from scratch.

Reviews land in `.review-log/`, named for the gate, path, artifact and timestamp. A
review that exists only in a session transcript is lost to a restart, and the finding
loop depends on the reviewer seeing what it already raised.

## Domain checks

The policy is domain-neutral. To add checks for your subject matter, copy
`tools/tech-lead-reviewer/reviewers/domain-checks.example.md` to
`.tech-lead/domain-checks.md` **in your project** — the dispatcher appends it under
`## Project domain checks`, and the gates refer to it. When the file doesn't exist
there are no domain checks, and the policy tells the reviewer their absence is not a
finding.

## How it hangs together

```
the tool (submodule)                 your project
────────────────────                 ────────────
reviewers/tech-lead-reviewer.md      .env
   canonical policy, the only          the only place a model is named
   file you edit                     .tech-lead/domain-checks.md
        │                              yours, optional
        │  bin/generate-adapters.py            │
        └──────────────────────────────────────┤
                                               ▼
                              .tech-lead/codex-tech-lead.toml
                              .tech-lead/claude-tech-lead.md
                              .tech-lead/hermes-tech-lead.md
                              .tech-lead/dispatch-instructions.md
                              .claude/agents/tech-lead-reviewer.md
                                 (second path only)
```

Every adapter records the sha256 of the policy it came from.
`generate-adapters.py --check` fails when one has drifted, so wire it into your
verification command and hand-editing a generated file becomes a failing build.

## Verdict semantics

`READY` is permitted only with zero Critical and zero Important findings. Any number
of Nits is compatible with it. Emitting `READY` alongside a Critical or Important
finding is a process failure equivalent to cheerleading — the verdict line and the
finding count have to agree at source.

A green verdict also requires citations. "Looks good" with no specific finding is not
an approval; it's the reviewer failing to do the job it was dispatched for.

## Status

Extracted from a working project after roughly a dozen real gate reviews. Expect it to
change as it gets used. Issues and pull requests welcome.

## License

MIT.

# tech-lead-reviewer-multi-agent

An independent, read-only technical reviewer for design and planning work, dispatched
at four gates and run on a model that didn't write the thing under review.

## Quickstart

**1. Add it to your project**

```sh
git submodule add https://github.com/dexmar/tech-lead-reviewer-multi-agent \
    tools/tech-lead-reviewer
```

**2. Configure the reviewer** — this is the only place a model is ever named

```sh
cp tools/tech-lead-reviewer/.env.example .env
```

```sh
TECH_LEAD_PROVIDER=codex          # needs the Codex CLI on PATH
TECH_LEAD_MODEL=gpt-5.6-sol
TECH_LEAD_EFFORT=max
```

**3. Generate** — writes into your repo, not the submodule

```sh
python3 tools/tech-lead-reviewer/bin/generate-adapters.py
```

**4. Tell your agent about it** — paste `.tech-lead/dispatch-instructions.md` into
your `AGENTS.md` or `CLAUDE.md`. It's generated to match your config.

**Run a gate:**

```sh
./tools/tech-lead-reviewer/bin/review-gate.sh 3 docs/specs/my-design.md
```

The review lands in `.review-log/` and prints to stdout. Gates are `1` approach,
`2` design section, `3` spec, `4` plan.

### Two optional extras

```sh
# A second, independent reviewer at gates 3 and 4, for comparison. Off by default.
TECH_LEAD_SECOND_ENABLED=true
TECH_LEAD_SECOND_MODEL=fable
TECH_LEAD_SECOND_EFFORT=max
```

```sh
# Checks specific to your subject matter, appended to the policy when present.
cp tools/tech-lead-reviewer/reviewers/domain-checks.example.md .tech-lead/domain-checks.md
```

Wire `generate-adapters.py --check` into your build and a hand-edited generated file
becomes a failing check.

---

## The one rule that matters

**The agent proposes a review. It never runs one unprompted, and never re-dispatches
on its own judgement.** After each review it presents every finding unaltered, and
you decide what gets fixed and whether another round happens.

This was learned the hard way. An automatic fix-and-re-review loop runs until the
reviewer runs out of objections, which is not the same as the artifact being right —
it starts manufacturing findings about work nobody has done yet, and spends real
reasoning on prose instead of on something checkable against reality.

The corollary: review is most valuable when a claim can be checked against something
concrete. Reviewing a spec for unwritten code produces opinions. Reviewing one whose
claims can be tested against real data produces bugs.

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

## Improving it

Because it is a submodule, changes travel back:

```sh
cd tools/tech-lead-reviewer
# edit reviewers/tech-lead-reviewer.md -- the canonical policy
git commit -am "..." && git push
cd ../.. && git add tools/tech-lead-reviewer && git commit -m "bump reviewer"
```

Two commits, and the separation is the point: a policy change cannot ride along
inside a project commit.

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

<!-- Generated from reviewers/tech-lead-reviewer.md; canonical-sha256: 70a80f9eb3006b21c0c5e647686fb87004e3f118dd125e0f72f367b89df12bef -->
# Tech Lead Review

Paste this section into the consuming project's `AGENTS.md`.

---

## Tech Lead Review

Load-bearing design and planning work passes four gates:

1. **Approach selected** — before presenting the first design section.
2. **Design section locked** — before moving to the next section. Applies
   only to a load-bearing section, not routine documentation or scaffolding.
3. **Specification finalized** — before asking the user to review it.
4. **Implementation plan finalized** — before implementing.

Run a gate with:

```
./bin/review-gate.sh <gate> <artifact-path> [prior-findings-file]
```

### The user authorizes every round

**Propose a gate review; do not run one unprompted, and never re-dispatch
on your own judgement.** After each review, present every Critical and
Important finding to the user unaltered, say what you propose to do about
each, and let the user decide what gets fixed and whether another round
runs at all.

This is deliberate. An automatic fix-and-re-review loop runs until the
reviewer runs out of objections, which is not the same as the artifact
being right — it manufactures findings about work nobody has done yet and
spends the reviewer's rigor on prose rather than on something checkable
against reality.

You may fix a finding, justify it with evidence in the artifact, or route
it onward unaltered. You may not downgrade, merge, or withhold one, and you
report what you did to each.

Reviews are written to `.review-log/` so a re-review can be given the prior
findings, and so a review survives a restart.

### Second path (disabled)

This project runs a single reviewer. To add a second opinion at gates 3
and 4, set `TECH_LEAD_SECOND_ENABLED=true` in `.env` and re-run
`bin/generate-adapters.py`.

### Runtime identity

The reviewer's provider, model, and effort come from `.env` and nowhere
else. Never pin a model in a generated adapter, and never vary the identity
between gates or passes. Record both the requested and the effective
identity with each review — they can differ.

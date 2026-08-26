<!-- Copy to reviewers/domain-checks.md and replace with your own. -->
<!-- If that file does not exist, there are no domain checks and the reviewer -->
<!-- is told that their absence is not a finding. -->

These checks apply to this project's subject matter. Apply the ones plausibly
relevant to the artifact under review; give a short not-applicable reason only for
checks somebody could reasonably have expected to apply.

## Ingestion and canonical events

- Identity merges and splits: does the design survive a source merging two records
  or splitting one?
- Duplicate and superseded records, and records the source publishes more than once.
- Historical corrections: can a re-import replace prior values without manual edits?
- Timezone and date boundaries, including events that cross midnight.
- Missing observations: are "not provided", "not applicable", "unknown" and
  "estimated" distinguishable, or flattened into one null?
- Idempotent re-import: does running the same import twice change anything?

## Derived values

- Formula version, constants, and eligibility rules — are they versioned with the
  output?
- Inputs: can a published value be reproduced from retained inputs alone?
- Recalculation: is it an explicit run, or an invisible side effect of deploying?

## Source terms

- Attribution or licensing conditions the source imposes on redistribution.
- Whether availability of a download implies permission to republish.

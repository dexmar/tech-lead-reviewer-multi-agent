#!/usr/bin/env bash
# Dispatch the Tech Lead reviewer for one gate.
#
# Usage: bin/review-gate.sh <1|2|3|4> <artifact-path> [prior-findings-file]
#
# Runs on the host: the Codex CLI and its credentials live under $HOME, outside
# any development container, so this is deliberately not a container-run command.
#
# This dispatches the primary path only. A second path, if enabled, is dispatched
# by the harness as a subagent -- see templates/dispatch-instructions.md.

set -euo pipefail

# Two roots, deliberately distinct. TOOL_ROOT is where this tool lives -- possibly a
# submodule inside somebody else's repository. PROJECT_ROOT is the repository being
# reviewed, which is what artifact paths, .env, domain checks and the review log all
# belong to. Conflating them means a vendored copy refuses every artifact in the
# project that vendored it.
TOOL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -n "${TECH_LEAD_PROJECT_ROOT:-}" ]; then
    PROJECT_ROOT="$TECH_LEAD_PROJECT_ROOT"
else
    # --show-superproject-working-tree is non-empty only when the working directory
    # sits inside a submodule, which is exactly the case --show-toplevel gets wrong.
    SUPERPROJECT="$(git rev-parse --show-superproject-working-tree 2>/dev/null || true)"
    if [ -n "$SUPERPROJECT" ]; then
        PROJECT_ROOT="$SUPERPROJECT"
    else
        PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$TOOL_ROOT")"
    fi
fi

POLICY="${TOOL_ROOT}/reviewers/tech-lead-reviewer.md"
DOMAIN="${PROJECT_ROOT}/.tech-lead/domain-checks.md"
LOG_DIR="${PROJECT_ROOT}/.review-log"

die() { printf 'review-gate: %s\n' "$1" >&2; exit 1; }

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    die "usage: bin/review-gate.sh <1|2|3|4> <artifact-path> [prior-findings-file]"
fi

GATE="$1"
case "$GATE" in
    1 | 2 | 3 | 4) ;;
    *) die "gate must be 1, 2, 3, or 4 (got: ${GATE})" ;;
esac

[ -f "$POLICY" ] || die "policy not found: ${POLICY}"
command -v codex >/dev/null 2>&1 || die "codex CLI not found on PATH"

# Runtime identity comes from the environment file and nowhere else.
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "${PROJECT_ROOT}/.env"
    set +a
fi

[ -n "${TECH_LEAD_PROVIDER:-}" ] || die "TECH_LEAD_PROVIDER is unset (see .env.example)"
[ -n "${TECH_LEAD_MODEL:-}" ] || die "TECH_LEAD_MODEL is unset (see .env.example)"
[ -n "${TECH_LEAD_EFFORT:-}" ] || die "TECH_LEAD_EFFORT is unset (see .env.example)"

if [ "$TECH_LEAD_PROVIDER" != "codex" ]; then
    die "TECH_LEAD_PROVIDER=${TECH_LEAD_PROVIDER} is not dispatched by this script.
It drives the Codex CLI. Another provider needs its own dispatcher that supplies
the same prompt: this policy, the gate, the artifact path, and its revision."
fi

# Arguments are data, never flags. The artifact must resolve inside the repository
# so a review cannot be pointed at an arbitrary path on the machine.
ARTIFACT_ARG="$2"
[ -f "$ARTIFACT_ARG" ] || die "artifact not found: ${ARTIFACT_ARG}"
ARTIFACT_ABS="$(cd "$(dirname "$ARTIFACT_ARG")" && pwd)/$(basename "$ARTIFACT_ARG")"
case "$ARTIFACT_ABS" in
    "${PROJECT_ROOT}/"*) ;;
    *) die "artifact must be inside ${PROJECT_ROOT}: ${ARTIFACT_ABS}" ;;
esac
ARTIFACT_REL="${ARTIFACT_ABS#"${PROJECT_ROOT}/"}"

PRIOR="${3-}"
if [ -n "$PRIOR" ] && [ ! -f "$PRIOR" ]; then
    die "prior findings file not found: ${PRIOR}"
fi

# A committed, unmodified artifact is identified by commit; anything else by digest,
# so a review always names bytes somebody can reproduce.
if git -C "$PROJECT_ROOT" diff --quiet HEAD -- "$ARTIFACT_REL" 2>/dev/null &&
    [ -z "$(git -C "$PROJECT_ROOT" ls-files --others --exclude-standard -- "$ARTIFACT_REL")" ]; then
    REVISION="$(git -C "$PROJECT_ROOT" rev-parse HEAD)"
else
    REVISION="sha256:$(shasum -a 256 "$ARTIFACT_ABS" | cut -d ' ' -f 1) (uncommitted)"
fi

TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

PROMPT_FILE="$(mktemp)"
trap 'rm -f "$PROMPT_FILE"' EXIT

{
    cat "$POLICY"
    # Domain checks are optional. Absent means there are none, not that they were
    # forgotten -- the policy says so explicitly.
    if [ -f "$DOMAIN" ]; then
        printf '\n---\n\n## Project domain checks\n\n'
        cat "$DOMAIN"
    fi
    printf '\n---\n\n# Dispatch\n\n'
    printf -- '- Gate: %s\n' "$GATE"
    printf -- '- Artifact: %s\n' "$ARTIFACT_REL"
    printf -- '- Artifact revision or SHA-256: %s\n' "$REVISION"
    printf -- '- Timestamp (ISO 8601 UTC): %s\n' "$TIMESTAMP"
    printf -- '- Requested provider/model/effort: %s / %s / %s\n' \
        "$TECH_LEAD_PROVIDER" "$TECH_LEAD_MODEL" "$TECH_LEAD_EFFORT"
    printf -- '- Read-only enforcement: sandbox (codex exec -s read-only)\n'
    printf '\nRead the artifact at the path above and review it against the Gate %s\n' "$GATE"
    printf 'criteria. Report the effective model and effort you are actually running as;\n'
    printf 'state unknown if the harness does not expose them.\n'
    if [ -n "$PRIOR" ]; then
        printf '\n## Prior findings and responses\n\n'
        cat "$PRIOR"
    fi
} >"$PROMPT_FILE"

mkdir -p "$LOG_DIR"
SLUG="$(printf '%s' "$ARTIFACT_REL" | tr '/.' '--')"
OUT="${LOG_DIR}/gate${GATE}-${TECH_LEAD_PROVIDER}-${SLUG}-$(date -u +%Y%m%dT%H%M%SZ).md"

# Codex echoes its banner and the full prompt to stderr. Useful for debugging and
# useless to the dispatcher, so it goes to a sidecar log; stdout stays the review.
TRANSCRIPT="${OUT%.md}.log"

if ! codex exec \
    --color never \
    -C "$PROJECT_ROOT" \
    -s read-only \
    -m "$TECH_LEAD_MODEL" \
    -c model_reasoning_effort="$TECH_LEAD_EFFORT" \
    -o "$OUT" \
    - <"$PROMPT_FILE" >/dev/null 2>"$TRANSCRIPT"; then
    printf 'review-gate: codex exec failed. Last lines of %s:\n' \
        "${TRANSCRIPT#"${PROJECT_ROOT}/"}" >&2
    tail -n 20 "$TRANSCRIPT" >&2
    exit 1
fi

[ -s "$OUT" ] || die "codex produced no review; see ${TRANSCRIPT#"${PROJECT_ROOT}/"}"

# The reviewer cannot observe its own identity from inside the sandbox and will
# honestly report it as unknown. Codex states it in the startup banner, so record it
# here -- an unverifiable effective identity defeats the point of the field.
banner_field() { head -n 20 "$TRANSCRIPT" | sed -n "s/^${1}: *//p" | head -n 1; }
{
    printf '\n---\n\nObserved by harness (codex startup banner)\n'
    printf -- '- Effective provider: %s\n' "$(banner_field 'provider')"
    printf -- '- Effective model: %s\n' "$(banner_field 'model')"
    printf -- '- Effective reasoning effort: %s\n' "$(banner_field 'reasoning effort')"
    printf -- '- Sandbox: %s\n' "$(banner_field 'sandbox')"
    printf -- '- Session id: %s\n' "$(banner_field 'session id')"
} >>"$OUT"

printf '# Tech Lead review — gate %s — %s\n\n' "$GATE" "$ARTIFACT_REL"
cat "$OUT"
printf '\n(review saved to %s)\n' "${OUT#"${PROJECT_ROOT}/"}"
printf '\nPresent these findings to the user and let them decide what to fix and\n'
printf 'whether another round runs. Do not re-dispatch on your own judgement.\n'

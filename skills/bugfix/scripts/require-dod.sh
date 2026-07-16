#!/usr/bin/env bash
# require-dod.sh
#
# PreToolUse hook for Claude Code that enforces the bugfix skill's
# Definition-of-Done checklist. Register in ~/.claude/settings.json under
# the hooks.PreToolUse array with matcher "Edit|Write|MultiEdit" for any
# source/test/docs path you want gated.
#
# Behaviour:
#   - If no DoD checklist file exists for this session, blocks with
#     exit 2 (Claude will see the stderr and stop).
#   - If any unchecked "- [ ]" box remains in the DoD file, blocks.
#   - Otherwise allows the tool call.
#
# The skill writes the DoD checklist to:
#   .bugfix/dod-<CLAUDE_SESSION_ID>.md
# at Phase 9 completion. The skill should *create* this file (empty
# with all boxes unchecked) at Phase 1 intake, and tick each box only
# when its evidence has been gathered.

set -euo pipefail

# Bypass entirely if not in a bugfix session. The bugfix skill writes a
# marker file when it activates. If absent, the hook is a no-op so
# normal edits aren't blocked.
marker=".bugfix/active-${CLAUDE_SESSION_ID:-unknown}"
if [[ ! -f "$marker" ]]; then
  exit 0
fi

state=".bugfix/dod-${CLAUDE_SESSION_ID:-unknown}.md"

if [[ ! -f "$state" ]]; then
  cat >&2 <<EOF
blocked by require-dod hook: bugfix DoD checklist missing.

The bugfix skill requires .bugfix/dod-<session>.md to exist before
edits are permitted in a bugfix session. Create the checklist at Phase 1
intake (skill's Definition-of-Done template) and tick boxes only when
their evidence has been gathered.
EOF
  exit 2
fi

# Allow Phase 1–8 edits: only block "final" edits if any DoD box is
# still unchecked AND we are past Phase 8. Phase tracking lives in a
# sibling file the skill maintains.
phase_file=".bugfix/phase-${CLAUDE_SESSION_ID:-unknown}"
current_phase="$(cat "$phase_file" 2>/dev/null || echo 0)"

if [[ "$current_phase" -ge 9 ]]; then
  if grep -q '^- \[ \]' "$state"; then
    cat >&2 <<EOF
blocked by require-dod hook: unchecked DoD items remain.

Unchecked boxes in $state:
$(grep -n '^- \[ \]' "$state" | head -20)

The bugfix skill is in Phase 9 (Definition of Done). All boxes must be
ticked with cited evidence before further edits are permitted. If you
genuinely need to edit (e.g., to address an item), regress the phase
counter and the gate the edit belongs to.
EOF
    exit 2
  fi
fi

exit 0

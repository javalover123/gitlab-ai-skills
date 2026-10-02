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
#   - Once the session reaches Phase 9, blocks if any unchecked "- [ ]" box
#     remains in the DoD file. Phases 1-8 are never blocked on this.
#   - Otherwise allows the tool call.
#
# The skill writes the DoD checklist to:
#   .bugfix/dod-<CLAUDE_SESSION_ID>.md
# at Phase 9 completion. The skill should *create* this file (empty
# with all boxes unchecked) at Phase 1 intake, and tick each box only
# when its evidence has been gathered.

set -euo pipefail

# Bypass entirely if there's no session ID to scope state to. Falling back to
# a shared constant (e.g. "unknown") here would let concurrent bugfix
# sessions in the same worktree collide on the same marker/state/phase files
# whenever CLAUDE_SESSION_ID isn't set, so treat "unset" the same as "not in
# a tracked bugfix session" rather than guessing an identity.
if [[ -z "${CLAUDE_SESSION_ID:-}" ]]; then
  exit 0
fi

# Bypass entirely if not in a bugfix session. The bugfix skill writes a
# marker file when it activates. If absent, the hook is a no-op so
# normal edits aren't blocked.
marker=".bugfix/active-${CLAUDE_SESSION_ID}"
if [[ ! -f "$marker" ]]; then
  exit 0
fi

state=".bugfix/dod-${CLAUDE_SESSION_ID}.md"

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
phase_file=".bugfix/phase-${CLAUDE_SESSION_ID}"
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

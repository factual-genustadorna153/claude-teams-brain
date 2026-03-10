#!/usr/bin/env bash
# claude-brain: SubagentStart hook
#
# Fires when a teammate is spawned. Reads agent_type from the event
# (the correct field per Claude Code docs), queries the brain for
# relevant role memory, and outputs it in the required hookSpecificOutput
# format so Claude Code injects it directly into the teammate's context.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="${SCRIPT_DIR}/brain_engine.py"
INPUT=$(cat)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# agent_type is the correct SubagentStart input field (not agent_name)
AGENT_TYPE=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print((d.get('agent_type', '') or 'general').lower().strip())
" 2>/dev/null || echo "general")

[ -z "$AGENT_TYPE" ] && AGENT_TYPE="general"

# Extract task description for relevance-ranked memory injection
TASK_DESC=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
# Try common field names for the task prompt
desc = (d.get('prompt') or d.get('task') or d.get('description') or d.get('message') or '')
print(str(desc)[:500])
" 2>/dev/null || echo "")

# Query brain for role-relevant memory, ranked by task relevance
CONTEXT=$(python3 "$ENGINE" query-role "$AGENT_TYPE" "$PROJECT_DIR" "$TASK_DESC" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('additionalContext',''))" \
  2>/dev/null || echo "")

# Tool-efficiency guidance injected into every teammate's context.
# Instructs agents to use the brain's MCP tools instead of raw Bash calls,
# reducing token consumption across the session.
TOOL_GUIDANCE="## Token-Efficient Tools (claude-teams-brain)
Prefer these MCP tools over direct Bash calls to minimise context usage:
- \`batch_execute\` — run multiple shell commands in a single call; all output is auto-indexed and searchable
- \`execute\` — run a single command with automatic output indexing
- \`search\` — query indexed output instead of re-running commands
- \`index\` — store any content in the session knowledge base for later retrieval
- \`stats\` — view token savings and call counts for this session

Always prefer \`batch_execute\` when issuing more than one shell command."

# Merge role memory with tool guidance; output even when no role memory exists.
if [ -n "$CONTEXT" ]; then
  FULL_CONTEXT="${CONTEXT}

${TOOL_GUIDANCE}"
else
  FULL_CONTEXT="$TOOL_GUIDANCE"
fi

# Output in the required hookSpecificOutput format.
# additionalContext inside hookSpecificOutput is injected directly into
# the teammate's context (not shown in the transcript as noisy output).
python3 -c "
import json, sys
ctx = sys.argv[1]
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'SubagentStart',
        'additionalContext': ctx
    }
}))
" "$FULL_CONTEXT"

exit 0

---
name: brain-status
description: |
  Show claude-teams-brain memory stats for this project
user_invocable: true
---

# brain-status

Show the current state of the claude-teams-brain memory index for this project.

## Instructions

Run:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brain_engine.py status "$CLAUDE_PROJECT_DIR"
```

Display the results in a clear, human-readable format:
- Total tasks indexed
- Total sessions recorded
- Decisions logged
- Files in the index
- Distinct agents seen
- Last activity timestamp

If the brain has data, show the 3 most recent task summaries.
If the brain is empty, tell the user memory will start building automatically once they run an Agent Team session.

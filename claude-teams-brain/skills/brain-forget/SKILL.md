---
name: brain-forget
description: |
  Remove a manually stored memory from the brain by partial text match.
  Use: /brain-forget <text>
user_invocable: true
---

# brain-forget

Remove a manual memory previously stored with `/brain-remember`. Partial matches are supported.

## Instructions

The user provides the text to match as an argument.

Run:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brain_engine.py forget "$ARGS" "$CLAUDE_PROJECT_DIR"
```

Show which memories were removed.
If no match is found, say so clearly and suggest using `/brain-status` to see what's stored.

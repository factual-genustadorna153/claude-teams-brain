---
name: brain-update
description: |
  Update claude-teams-brain from GitHub.
  Pulls latest changes, syncs to plugin cache, and reports what changed.
  Trigger: /brain-update
user_invocable: true
---

# brain-update

Pull the latest version of claude-teams-brain from GitHub and sync it to the local plugin cache.

## Instructions

1. Derive the **plugin root** from this skill's base directory (go up 2 levels — remove `/skills/brain-update`).
2. Run the update script with Bash:
   ```
   bash "<PLUGIN_ROOT>/scripts/update.sh"
   ```
3. After the script completes, display the results as markdown directly in the conversation:
   ```
   ## claude-teams-brain update
   - [x] Pulled latest from GitHub
   - [x] Synced to plugin cache
   - [x] Version: <version>
   - [x] Changes: <summary of changed files or "already up to date">
   ```
   Use `[x]` for success, `[ ]` for skipped or failed steps.
   If new hooks or settings were added, tell the user to **restart their Claude Code session** to apply them.

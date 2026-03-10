#!/usr/bin/env bash
# claude-teams-brain: update script
#
# Pulls the latest version from GitHub and syncs it into the plugin cache.
# Called by the /brain-update command.

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGINS_DIR="$(cd "${PLUGIN_ROOT}/../../../.." && pwd)"
MARKETPLACE_DIR="${PLUGINS_DIR}/marketplaces/claude-teams-brain"
REPO_URL="https://github.com/Gr122lyBr/claude-teams-brain.git"

echo "==> Plugin root:     $PLUGIN_ROOT"
echo "==> Marketplace dir: $MARKETPLACE_DIR"

# --- 1. Ensure marketplace clone exists (auto-clone if missing) ---
if [ ! -d "$MARKETPLACE_DIR/.git" ]; then
  echo ""
  echo "==> Marketplace clone not found — cloning fresh..."
  mkdir -p "$(dirname "$MARKETPLACE_DIR")"
  git clone "$REPO_URL" "$MARKETPLACE_DIR"
  echo "    Cloned successfully."
else
  echo ""
  echo "==> Pulling latest from GitHub..."
  cd "$MARKETPLACE_DIR"
  git fetch origin
  BEFORE=$(git rev-parse HEAD)
  git pull --ff-only origin "$(git symbolic-ref --short HEAD)"
  AFTER=$(git rev-parse HEAD)

  if [ "$BEFORE" = "$AFTER" ]; then
    echo "    Already up to date ($(git rev-parse --short HEAD))"
  else
    echo "    Updated: $(git rev-parse --short "$BEFORE")..$(git rev-parse --short "$AFTER")"
    CHANGED=$(git diff --name-only "$BEFORE" "$AFTER" | head -20 || echo "unknown")
    echo "    Changed files:"
    echo "$CHANGED" | sed 's/^/      /'
  fi
fi

# --- 2. Read new version from source ---
PLUGIN_SRC="${MARKETPLACE_DIR}/claude-teams-brain"
NEW_VERSION=$(node -p "require('${PLUGIN_SRC}/package.json').version" 2>/dev/null || echo "")

if [ -z "$NEW_VERSION" ]; then
  echo "ERROR: Could not read version from ${PLUGIN_SRC}/package.json"
  exit 1
fi
echo ""
echo "==> New version: $NEW_VERSION"

# --- 3. Sync to cache, creating new versioned dir if version changed ---
CACHE_BASE="${PLUGINS_DIR}/cache/claude-teams-brain/claude-teams-brain"
NEW_CACHE_DIR="${CACHE_BASE}/${NEW_VERSION}"

mkdir -p "$NEW_CACHE_DIR"
echo "==> Syncing to cache: $NEW_CACHE_DIR"
rsync -a --delete --exclude='.git' "${PLUGIN_SRC}/" "${NEW_CACHE_DIR}/"
echo "    Sync complete."

# --- 4. Update installed_plugins.json with new version and path ---
INSTALLED_JSON="${PLUGINS_DIR}/installed_plugins.json"

if [ -f "$INSTALLED_JSON" ]; then
  echo "==> Updating installed_plugins.json..."
  python3 - <<PYEOF
import json, sys, os

path = "${INSTALLED_JSON}"
new_version = "${NEW_VERSION}"
new_cache_dir = "${NEW_CACHE_DIR}"

with open(path, 'r') as f:
    data = json.load(f)

key = "claude-teams-brain@claude-teams-brain"
if key in data.get("plugins", {}):
    entries = data["plugins"][key]
    for entry in entries:
        entry["version"] = new_version
        entry["installPath"] = new_cache_dir
        entry["lastUpdated"] = __import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    data["plugins"][key] = entries
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"    Updated to v{new_version} at {new_cache_dir}")
else:
    print(f"    WARN: key '{key}' not found in installed_plugins.json — skipping")
PYEOF
else
  echo "WARN: installed_plugins.json not found at $INSTALLED_JSON — skipping."
fi

echo ""
echo "==> Done. Restart Claude Code to apply the update."

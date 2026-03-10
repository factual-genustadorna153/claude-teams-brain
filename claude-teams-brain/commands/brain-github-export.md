Export all accumulated brain knowledge as `CONVENTIONS.md` and open a GitHub Pull Request so your whole team can review what the AI team learned. Requires `gh` CLI to be installed and authenticated.

Run `/brain-github-export` to export and open a PR in the current project's GitHub repository. A GitHub Actions workflow template is also available at `${CLAUDE_PLUGIN_ROOT}/profiles/github-actions-conventions.yml` — copy it to `.github/workflows/` in your repo for automatic PR creation after every session.

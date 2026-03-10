# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report them privately via [GitHub Security Advisories](https://github.com/Gr122lyBr/claude-teams-brain/security/advisories/new).

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional)

You can expect an initial response within 48 hours and a fix within 7 days for confirmed issues.

## Security Model

- All memory is stored **locally** in `~/.claude-teams-brain/projects/<project-hash>/brain.db`
- No data is transmitted to any external server
- The MCP server runs as a local subprocess with no network access
- Shell commands executed via `batch_execute` / `execute` run with the same permissions as the Claude Code process

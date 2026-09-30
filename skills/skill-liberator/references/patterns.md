# Claude-ism pattern catalog

Constructs that tie a skill to Claude Code, what `liberate.py` does with each, and what still needs a human.

## Auto-rewritten

| Pattern | Example | Rewrite |
|---|---|---|
| `allowed-tools` frontmatter | `allowed-tools: Read, Bash` | Line removed; tool permissions belong to the target harness |
| `model` frontmatter | `model: claude-opus-4-6` | Line removed; model choice belongs to the target harness |
| Config paths | `~/.claude/settings.json` | `{harness-config-dir}/settings.json` |
| Slash commands (built-in) | `` `/compact` `` | `start a fresh context summary` (see mapping in `liberate.py`) |
| Slash commands (custom) | `` `/my-skill` `` | `the "my-skill" capability` |
| Argument templating | `$ARGUMENTS` | `{arguments}` |
| Product reference | `Claude Code` | `the original harness` |
| Vendor reference | `Anthropic` | `the model vendor` |
| Agent self-reference | `You are Claude` | `You are the agent` |

## Flagged for human review

| Pattern | Example | Why it needs a human |
|---|---|---|
| MCP server config | fenced block containing `mcpServers` | MCP wiring is harness-specific; recreate the integration |
| `.mcp.json` references | `Add this to .mcp.json` | Same as above |
| Unknown slash commands | `` `/frobnicate` `` | The script rewrites these generically; check the meaning fits |
| Harness CLI calls in scripts | `claude mcp add ...` | Scripts must not shell out to the original harness |
| Credential setup steps | `export ANTHROPIC_API_KEY=...` | Only valid if the target harness uses the same credential |

## Deliberately untouched

- URLs, file paths that are not `~/.claude`, and code samples that merely mention a slash-like path (`/api/v1/items`).
- License files and attribution: kept verbatim.

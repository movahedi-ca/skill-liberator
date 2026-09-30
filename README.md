# skill-liberator

Use Claude-Code-authored agent skills in any agent harness.

A skill written for Claude Code is full of harness-specific constructs: `/slash-command` invocations, `~/.claude` paths, `$ARGUMENTS` templating, `allowed-tools` frontmatter, and MCP server config blocks that only Claude Code understands. `skill-liberator` ports such a skill to harness-neutral form so it works in Muse, Gemini CLI, or anything else.

## How it works

A deterministic, offline, stdlib-only Python CLI scans the skill and rewrites what it can, flags what it cannot:

```bash
python3 skills/skill-liberator/scripts/liberate.py /path/to/claude-skill --out /path/to/skill-ported
```

It prints a JSON report to stdout: every finding with file, line, kind, and action (`rewrote`, `removed`, `needs_human`). Exit 0 means fully automatic; exit 1 means a human should review the flagged items (usually MCP wiring, which is harness-specific by nature).

| Claude-ism | Becomes |
|---|---|
| `` `/compact` `` | `start a fresh context summary` |
| `` `/my-skill` `` | `the "my-skill" capability` |
| `$ARGUMENTS` | `{arguments}` |
| `~/.claude/x.json` | `{harness-config-dir}/x.json` |
| `allowed-tools:` / `model:` frontmatter | removed |
| `You are Claude, running inside Claude Code` | `You are the agent, running inside the original harness` |
| MCP config block | kept, with a human-review note above it |

See `skills/skill-liberator/examples/before-after.md` for a full before/after example, and `skills/skill-liberator/references/patterns.md` for the pattern catalog.

## The skill

`skills/skill-liberator/SKILL.md` is the adapter skill itself, written harness-neutral so any agent can follow it: run the script, review the `needs_human` findings, sanity-check the automatic rewrites, verify with a second run.

## Use it as a skill

Copy `skills/skill-liberator/` into your harness skills directory, or point your agent at its `SKILL.md`. It has no dependencies beyond Python 3.

## Tests

```bash
python3 -m unittest discover -s tests
```

No commit lands unless the suite is green on the changed code.

## License

MIT. See `LICENSE`.

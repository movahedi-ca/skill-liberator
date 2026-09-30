# Before / after: porting a fictional `meeting-notes` skill

Input: a small Claude-Code-authored skill (invented for this example).

## Before (`SKILL.md`, excerpt)

```markdown
---
name: meeting-notes
description: Turn a transcript into structured meeting notes. Use `/meeting-notes $ARGUMENTS`.
allowed-tools: Read, Write, Bash
---

# Meeting Notes

You are Claude, running inside Claude Code. Take the transcript passed as $ARGUMENTS
and produce notes. If the context gets long, run `/compact` first.

Your config lives at ~/.claude/meeting-notes.json. Edit it to change the template.

MCP setup for the calendar integration:

```json
{
  "mcpServers": {
    "calendar": {"command": "npx", "args": ["-y", "@acme/calendar-mcp"]}
  }
}
```

Built by Acme, tested on Anthropic models.
```

## Command

```bash
python3 scripts/liberate.py ./meeting-notes --out ./meeting-notes-ported
```

## After (`meeting-notes-ported/SKILL.md`, excerpt)

```markdown
---
name: meeting-notes
description: Turn a transcript into structured meeting notes. Use the "meeting-notes" capability {arguments}.
---

# Meeting Notes

You are the agent, running inside the original harness. Take the transcript passed as {arguments}
and produce notes. If the context gets long, run start a fresh context summary first.

Your config lives at {harness-config-dir}/meeting-notes.json. Edit it to change the template.

MCP setup for the calendar integration:

> NOTE (harness port): the block below configures an MCP server for the original harness. Kept for reference; recreate the equivalent integration in your harness.
```json
{
  "mcpServers": {
    "calendar": {"command": "npx", "args": ["-y", "@acme/calendar-mcp"]}
  }
}
```

Built by Acme, tested on the model vendor models.
```

## Report summary

11 findings: 10 auto-resolved (frontmatter removed, paths, slash commands, `$ARGUMENTS`, product and model references), 1 flagged for human review (the MCP block). A human then writes the calendar integration for the target harness and re-runs the tool until the report is clean.

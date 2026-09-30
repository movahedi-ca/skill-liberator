#!/usr/bin/env python3
"""Port a Claude-Code-authored agent skill to harness-neutral form.

Reads a skill directory, detects Claude-Code-specific constructs, and writes
a ported copy plus a machine-readable report.

Usage:
    python3 liberate.py SOURCE_DIR [--out OUT_DIR]

The report (JSON) goes to stdout. The ported skill tree goes to OUT_DIR
(default: SOURCE_DIR + "-liberated").

Exit codes: 0 = ported, nothing needs a human; 1 = ported, some items need
a human eye (see the report); 2 = usage error.

The porting is deterministic, offline, and stdlib-only. It never executes
the skill's code; it only rewrites text.

Rewrites applied:
  - SKILL.md frontmatter `allowed-tools:` / `model:` lines are removed
    (tool permissions belong to the target harness).
  - `~/.claude/...` paths become `{harness-config-dir}/...`.
  - Slash-command invocations (`/compact`, `/init`, custom `/foo`) become
    plain-language capability references.
  - `$ARGUMENTS` templating becomes `{arguments}`.
  - `Claude Code` becomes `the original harness`; standalone `Claude`
    (the agent) becomes `the agent`.
  - MCP server config blocks are KEPT but flagged for human review, with a
    note inserted above the block.

Everything the tool cannot safely rewrite is left in place and reported
with action "needs_human".
"""
import argparse
import json
import os
import re
import shutil
import sys

VERSION = "0.1.0"

TEXT_EXTS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".sh",
    ".py", ".js", ".ts", ".cjs", ".mjs",
}

# Built-in Claude Code slash commands mapped to plain-language equivalents.
SLASH_COMMANDS = {
    "compact": "start a fresh context summary",
    "init": "initialize the project for the agent harness",
    "clear": "clear the conversation context",
    "help": "the harness help",
    "config": "the harness settings",
    "model": "the harness model selector",
    "memory": "the harness memory controls",
    "permissions": "the harness permission settings",
    "review": "a code review pass",
    "mcp": "the harness integration settings",
    "agents": "the subagent controls",
    "status": "the harness status display",
    "hooks": "the harness hook configuration",
    "pr": "a pull-request workflow",
    "login": "the harness sign-in",
    "logout": "the harness sign-out",
    "doctor": "the harness diagnostics",
    "vim": "the harness editor mode",
    "cost": "the harness usage display",
    "resume": "resume a previous session",
}

# A backticked span that opens with a slash command: `/cmd` or `/cmd rest...`.
# The name must not be followed by / (that is a URL or file path, not a command).
SLASH_RE = re.compile(r"`/([a-z][a-z0-9_-]{0,30})(?![\w/])([^`]*)`")
# A bare slash command: not part of a path, URL, or word.
SLASH_BARE_RE = re.compile(r"(?<![\w/`'\"])/([a-z][a-z0-9_-]{1,30})(?![\w/])")

CLAUDE_CODE_RE = re.compile(r"\bClaude Code\b")
CLAUDE_ALONE_RE = re.compile(r"(?<!\bClaude )\bClaude\b(?! Code\b)")
ANTHROPIC_RE = re.compile(r"\bAnthropic\b")

CONFIG_PATH_RE = re.compile(r"~/\.claude(/[^\s`\"')\]]*)?")
ARGUMENTS_RE = re.compile(r"\$ARGUMENTS\b")

FRONTMATTER_DROP_RE = re.compile(r"^(allowed-tools|model)\s*:")

MCP_MARKERS = ("mcpservers", ".mcp.json", "modelcontextprotocol")

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})")


def slash_replacement(name):
    plain = SLASH_COMMANDS.get(name)
    if plain:
        return plain
    return 'the "%s" capability' % name


def port_line(line, findings, rel, lineno):
    """Apply line-level rewrites. Returns (new_line, drop_line)."""
    stripped = line.lstrip()

    # Frontmatter lines that belong to the original harness.
    if FRONTMATTER_DROP_RE.match(stripped):
        key = stripped.split(":", 1)[0]
        findings.append({
            "file": rel, "line": lineno, "kind": "frontmatter",
            "action": "removed",
            "detail": "Removed harness-specific frontmatter '%s:'; "
                      "tool permissions and model choice belong to the "
                      "target harness." % key,
        })
        return line, True

    new = line

    def note(kind, action, detail):
        findings.append({
            "file": rel, "line": lineno, "kind": kind,
            "action": action, "detail": detail,
        })

    # Backticked slash commands first, then bare ones. Slash rewrites run
    # before config-path rewrites so path segments are never mistaken
    # for commands.
    def backticked_sub(m):
        name = m.group(1)
        rest = m.group(2)
        note("slash-command", "rewrote",
             "Replaced slash command '/%s' with a plain-language "
             "capability reference." % name)
        return slash_replacement(name) + rest
    new = SLASH_RE.sub(backticked_sub, new)

    def bare_sub(m):
        name = m.group(1)
        note("slash-command", "rewrote",
             "Replaced slash command '/%s' with a plain-language "
             "capability reference." % name)
        return slash_replacement(name)
    new = SLASH_BARE_RE.sub(bare_sub, new)

    # ~/.claude paths.
    def config_sub(m):
        rest = m.group(1) or ""
        note("config-path", "rewrote",
             "Replaced Claude Code config path with a harness-neutral "
             "placeholder; substitute your harness config directory.")
        return "{harness-config-dir}" + rest
    new = CONFIG_PATH_RE.sub(config_sub, new)

    # $ARGUMENTS templating.
    if ARGUMENTS_RE.search(new):
        note("arguments-template", "rewrote",
             "Replaced $ARGUMENTS with {arguments}, a harness-neutral "
             "template placeholder.")
        new = ARGUMENTS_RE.sub("{arguments}", new)

    # Product and model references.
    if CLAUDE_CODE_RE.search(new):
        note("product-reference", "rewrote",
             "Replaced 'Claude Code' with 'the original harness'.")
        new = CLAUDE_CODE_RE.sub("the original harness", new)
    if ANTHROPIC_RE.search(new):
        note("product-reference", "rewrote",
             "Replaced 'Anthropic' with 'the model vendor'.")
        new = ANTHROPIC_RE.sub("the model vendor", new)
    if CLAUDE_ALONE_RE.search(new):
        note("model-reference", "rewrote",
             "Replaced standalone 'Claude' with 'the agent'.")
        new = CLAUDE_ALONE_RE.sub("the agent", new)

    return new, False


def port_text(rel, text, findings):
    """Port one text file. Handles MCP fenced blocks specially."""
    lines = text.split("\n")
    out = []
    i = 0
    dropped_frontmatter = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if m:
            fence = m.group(2)
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith(fence[0] * 3):
                j += 1
            block = "\n".join(lines[i:j + 1])
            lowered = block.lower()
            if any(marker in lowered for marker in MCP_MARKERS):
                findings.append({
                    "file": rel, "line": i + 1, "kind": "mcp-config",
                    "action": "needs_human",
                    "detail": "MCP server config block kept for reference. "
                              "Recreate the equivalent integration in the "
                              "target harness; MCP wiring is harness-specific.",
                })
                out.append(
                    "> NOTE (harness port): the block below configures an "
                    "MCP server for the original harness. Kept for reference; "
                    "recreate the equivalent integration in your harness."
                )
                out.extend(lines[i:j + 1])
                i = j + 1
                continue
            out.append(lines[i])
            i += 1
            continue
        new_line, drop = port_line(lines[i], findings, rel, i + 1)
        if drop:
            dropped_frontmatter += 1
        else:
            out.append(new_line)
        i += 1
    return "\n".join(out), dropped_frontmatter


def is_text_file(name):
    return os.path.splitext(name)[1].lower() in TEXT_EXTS


def liberate(source, out_dir):
    findings = []
    files_scanned = 0
    files_ported = 0

    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    for root, dirs, files in os.walk(source):
        dirs.sort()
        for name in sorted(files):
            src_path = os.path.join(root, name)
            rel = os.path.relpath(src_path, source)
            dst_path = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            if is_text_file(name):
                files_scanned += 1
                try:
                    with open(src_path, "r", encoding="utf-8") as f:
                        text = f.read()
                except OSError:
                    shutil.copy2(src_path, dst_path)
                    findings.append({
                        "file": rel, "line": 0, "kind": "unreadable",
                        "action": "needs_human",
                        "detail": "Could not read file; copied unchanged.",
                    })
                    continue
                ported, _ = port_text(rel, text, findings)
                with open(dst_path, "w", encoding="utf-8") as f:
                    f.write(ported)
                files_ported += 1
            else:
                shutil.copy2(src_path, dst_path)

    auto = sum(1 for f in findings if f["action"] != "needs_human")
    needs_human = sum(1 for f in findings if f["action"] == "needs_human")
    report = {
        "tool": "liberate",
        "version": VERSION,
        "source": os.path.abspath(source),
        "out": os.path.abspath(out_dir),
        "files_scanned": files_scanned,
        "files_ported": files_ported,
        "findings": findings,
        "summary": {"auto": auto, "needs_human": needs_human},
        "status": "needs_human" if needs_human else "clean",
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Port a Claude-Code-authored agent skill to harness-neutral form."
    )
    parser.add_argument("source", help="skill directory to port")
    parser.add_argument("--out", default=None, help="output directory")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.source):
        print("Not a directory: %s" % args.source, file=sys.stderr)
        return 2
    out_dir = args.out or (args.source.rstrip(os.sep) + "-liberated")
    report = liberate(args.source, out_dir)
    print(json.dumps(report, indent=2))
    return 1 if report["summary"]["needs_human"] else 0


if __name__ == "__main__":
    sys.exit(main())

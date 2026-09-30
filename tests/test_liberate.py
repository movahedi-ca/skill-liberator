"""Tests for scripts/liberate.py. Run: python3 -m unittest discover -s tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

LIBERATE = os.path.join(
    os.path.dirname(__file__), "..", "skills", "skill-liberator",
    "scripts", "liberate.py",
)

FIXTURE = """---
name: meeting-notes
description: Turn a transcript into notes. Use `/meeting-notes $ARGUMENTS`.
allowed-tools: Read, Write, Bash
model: claude-opus-4-6
---

# Meeting Notes

You are Claude, running inside Claude Code. Take the transcript passed as $ARGUMENTS
and produce notes. If the context gets long, run `/compact` first.

Your config lives at ~/.claude/meeting-notes.json.

MCP setup:

```json
{
  "mcpServers": {
    "calendar": {"command": "npx", "args": ["-y", "@acme/calendar-mcp"]}
  }
}
```

Built by Acme, tested on Anthropic models.
"""


class LiberateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="liberate-test-")
        self.src = os.path.join(self.tmp, "meeting-notes")
        os.makedirs(self.src)
        with open(os.path.join(self.src, "SKILL.md"), "w") as f:
            f.write(FIXTURE)
        with open(os.path.join(self.src, "notes.txt"), "w") as f:
            f.write("plain notes, nothing harness specific\n")
        self.out = os.path.join(self.tmp, "out")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_liberate(self, *args):
        proc = subprocess.run(
            [sys.executable, LIBERATE] + list(args),
            capture_output=True, text=True,
        )
        return proc

    def test_full_port_needs_human_for_mcp(self):
        proc = self.run_liberate(self.src, "--out", self.out)
        self.assertEqual(proc.returncode, 1)
        report = json.loads(proc.stdout)
        self.assertEqual(report["tool"], "liberate")
        self.assertEqual(report["status"], "needs_human")
        self.assertEqual(report["files_scanned"], 2)
        kinds = {f["kind"] for f in report["findings"]}
        for expected in ("frontmatter", "arguments-template", "slash-command",
                         "config-path", "model-reference",
                         "product-reference", "mcp-config"):
            self.assertIn(expected, kinds)

    def test_ported_output_is_clean(self):
        proc = self.run_liberate(self.src, "--out", self.out)
        self.assertEqual(proc.returncode, 1)
        with open(os.path.join(self.out, "SKILL.md")) as f:
            ported = f.read()
        for banned in ("~/.claude", "$ARGUMENTS", "/compact",
                       "allowed-tools:", "model:", "Claude Code"):
            self.assertNotIn(banned, ported)
        # No slash-command invocations survive (the skill name in the
        # frontmatter and inside the config placeholder is fine).
        self.assertNotIn("`/meeting-notes", ported)
        self.assertNotIn("run /compact", ported)
        # Config path survived as a placeholder, not a rewrite casualty.
        self.assertIn("{harness-config-dir}/meeting-notes.json", ported)
        self.assertIn("{arguments}", ported)
        self.assertIn("start a fresh context summary", ported)
        self.assertIn("the agent, running inside the original harness", ported)
        # MCP block kept with the human-review note.
        self.assertIn("mcpServers", ported)
        self.assertIn("NOTE (harness port)", ported)
        # Untouched file copied verbatim.
        with open(os.path.join(self.out, "notes.txt")) as f:
            self.assertEqual(f.read(), "plain notes, nothing harness specific\n")

    def test_clean_skill_exits_zero(self):
        clean = os.path.join(self.tmp, "clean")
        os.makedirs(clean)
        with open(os.path.join(clean, "SKILL.md"), "w") as f:
            f.write("---\nname: plain\n---\n\n# Plain\n\nDo the thing.\n")
        proc = self.run_liberate(clean, "--out", self.out)
        self.assertEqual(proc.returncode, 0)
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["findings"], [])

    def test_missing_dir_exits_two(self):
        proc = self.run_liberate(os.path.join(self.tmp, "nope"),
                                 "--out", self.out)
        self.assertEqual(proc.returncode, 2)

    def test_default_out_dir(self):
        proc = self.run_liberate(self.src)
        self.assertIn(proc.returncode, (0, 1))
        report = json.loads(proc.stdout)
        self.assertTrue(report["out"].endswith("meeting-notes-liberated"))
        self.assertTrue(os.path.isdir(report["out"]))
        shutil.rmtree(report["out"], ignore_errors=True)

    def test_findings_carry_file_and_line(self):
        proc = self.run_liberate(self.src, "--out", self.out)
        report = json.loads(proc.stdout)
        for finding in report["findings"]:
            self.assertIn("file", finding)
            self.assertIn("line", finding)
            self.assertIn("kind", finding)
            self.assertIn("action", finding)
            self.assertIn(finding["action"], ("rewrote", "removed",
                                             "needs_human"))

    def test_path_segments_not_treated_as_commands(self):
        skill = os.path.join(self.tmp, "paths")
        os.makedirs(skill)
        with open(os.path.join(skill, "SKILL.md"), "w") as f:
            f.write("Fetch `/api/v1/items` then check ~/.claude/cache.\n")
        proc = self.run_liberate(skill, "--out", self.out)
        with open(os.path.join(self.out, "SKILL.md")) as f:
            ported = f.read()
        self.assertIn("/api/v1/items", ported)
        self.assertIn("{harness-config-dir}/cache", ported)


if __name__ == "__main__":
    unittest.main()

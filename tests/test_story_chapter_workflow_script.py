from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class StoryChapterWorkflowScriptTest(unittest.TestCase):
    def test_algorithm_story_chapter_workflow_script_runs_when_executed_directly(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/algorithm/story_chapter/run_workflow.py", "--help"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Run story chapter workflow", result.stdout)


if __name__ == "__main__":
    unittest.main()

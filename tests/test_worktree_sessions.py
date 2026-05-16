import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class WorktreeSessionTests(unittest.TestCase):
    def test_create_task_worktree_uses_clean_base_and_copies_support_state(self) -> None:
        from agent_team.harness_paths import default_state_root
        from agent_team.worktree_sessions import create_task_worktree

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
            (repo_root / "README.md").write_text("# main branch\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True, capture_output=True, text=True)

            subprocess.run(["git", "checkout", "-b", "test"], cwd=repo_root, check=True, capture_output=True, text=True)
            (repo_root / "README.md").write_text("# clean test branch\n")
            subprocess.run(["git", "commit", "-am", "test baseline"], cwd=repo_root, check=True, capture_output=True, text=True)

            subprocess.run(
                ["git", "checkout", "-b", "feature/current"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
            (repo_root / "README.md").write_text("# dirty current branch\n")
            subprocess.run(["git", "commit", "-am", "current work"], cwd=repo_root, check=True, capture_output=True, text=True)

            state_root = default_state_root(repo_root=repo_root)
            state_root.mkdir(parents=True, exist_ok=True)
            (state_root / "executor-env.json").write_text(
                '{"inherit":[],"inherit_prefixes":[],"set":{"FOO":"BAR"},"unset":[]}\n'
            )
            (state_root / "skill-preferences.yaml").write_text("initialized: true\n")
            (state_root / "local").mkdir(parents=True, exist_ok=True)
            (state_root / "local" / "verification-private.json").write_text(
                '{"default":{"base_url":"https://example.test"}}\n'
            )
            (state_root / "memory" / "Implementation").mkdir(parents=True, exist_ok=True)
            (state_root / "memory" / "Implementation" / "lessons.md").write_text("remember\n")
            (state_root / "_runtime" / "sessions" / "old").mkdir(parents=True, exist_ok=True)
            (state_root / "_runtime" / "sessions" / "old" / "session.json").write_text("{}\n")
            (state_root / "session-index.json").write_text(json.dumps({"sessions": [{"session_id": "old"}]}))
            (state_root / "local" / "worktree-policy.json").write_text(
                json.dumps(
                    {
                        "base_ref_candidates": ["missing", "test"],
                        "branch_prefix": "feature/",
                        "worktree_root": ".worktrees",
                        "date_format": "%Y%m%d",
                        "slug_max_length": 40,
                        "naming_mode": "request_summary_with_fallback",
                    }
                )
            )

            worktree = create_task_worktree(
                project_root=repo_root,
                source_state_root=state_root,
                message="新增 登录 按钮",
            )

            self.assertEqual(worktree.base_ref, "test")
            self.assertRegex(worktree.branch, r"^feature/\d{8}-add-login-button$")
            self.assertEqual((worktree.path / "README.md").read_text(), "# clean test branch\n")
            self.assertTrue((worktree.path / ".agt" / "executor-env.json").exists())
            self.assertTrue((worktree.path / ".agt" / "skill-preferences.yaml").exists())
            self.assertTrue((worktree.path / ".agt" / "local" / "verification-private.json").exists())
            self.assertTrue((worktree.path / ".agt" / "memory" / "Implementation" / "lessons.md").exists())
            self.assertFalse((worktree.path / ".agt" / "_runtime").exists())
            self.assertFalse((worktree.path / ".agt" / "session-index.json").exists())
            self.assertEqual(worktree.worktree_policy_source, "local_file")
            self.assertEqual(worktree.naming_source, "request_summary")
            self.assertEqual(
                json.loads(worktree.worktree_policy_snapshot_path.read_text())["base_ref_candidates"],
                ["missing", "test"],
            )

    def test_create_task_worktree_adds_unique_suffix_when_names_collide(self) -> None:
        from agent_team.harness_paths import default_state_root
        from agent_team.worktree_sessions import create_task_worktree

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
            (repo_root / "README.md").write_text("# test repo\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "branch", "-m", "main"], cwd=repo_root, check=True, capture_output=True, text=True)

            state_root = default_state_root(repo_root=repo_root)
            (state_root / "local").mkdir(parents=True, exist_ok=True)
            (state_root / "local" / "worktree-policy.json").write_text(
                json.dumps({"base_ref_candidates": ["main"]})
            )

            first = create_task_worktree(project_root=repo_root, source_state_root=state_root, message="fix api")
            second = create_task_worktree(project_root=repo_root, source_state_root=state_root, message="fix api")

            self.assertNotEqual(first.branch, second.branch)
            self.assertTrue(second.branch.endswith("-2"))
            self.assertTrue(second.path.name.endswith("-2"))


if __name__ == "__main__":
    unittest.main()

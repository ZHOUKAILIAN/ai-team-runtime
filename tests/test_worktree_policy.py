import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class WorktreePolicyTests(unittest.TestCase):
    def test_load_worktree_policy_uses_builtin_defaults_when_missing(self) -> None:
        from agent_team.worktree_policy import load_worktree_policy

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir) / ".agt"
            policy = load_worktree_policy(state_root)

            self.assertEqual(policy.base_ref_candidates, ("origin/test", "origin/main", "test", "main"))
            self.assertEqual(policy.branch_prefix, "feature/")
            self.assertEqual(policy.worktree_root, ".worktrees")
            self.assertEqual(policy.date_format, "%Y%m%d")
            self.assertEqual(policy.slug_max_length, 40)
            self.assertEqual(policy.naming_mode, "request_summary_with_fallback")
            self.assertEqual(policy.source, "builtin_default")

    def test_load_worktree_policy_reads_local_file(self) -> None:
        from agent_team.worktree_policy import load_worktree_policy, worktree_policy_path

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir) / ".agt"
            path = worktree_policy_path(state_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "base_ref_candidates": ["release", "main"],
                        "branch_prefix": "bugfix",
                        "worktree_root": ".sandbox-worktrees",
                        "date_format": "%Y%m%d",
                        "slug_max_length": 24,
                        "naming_mode": "request_summary_with_fallback",
                    }
                )
            )

            policy = load_worktree_policy(state_root)

            self.assertEqual(policy.base_ref_candidates, ("release", "main"))
            self.assertEqual(policy.branch_prefix, "bugfix/")
            self.assertEqual(policy.worktree_root, ".sandbox-worktrees")
            self.assertEqual(policy.slug_max_length, 24)
            self.assertEqual(policy.source, "local_file")

    def test_load_worktree_policy_rejects_invalid_json(self) -> None:
        from agent_team.worktree_policy import load_worktree_policy, worktree_policy_path

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir) / ".agt"
            path = worktree_policy_path(state_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not-json")

            with self.assertRaisesRegex(ValueError, "Invalid worktree policy JSON"):
                load_worktree_policy(state_root)

    def test_summarize_request_slug_translates_common_terms_and_falls_back(self) -> None:
        from agent_team.worktree_policy import summarize_request_slug

        slug, source = summarize_request_slug("新增 登录 按钮", max_length=40)
        self.assertEqual(slug, "add-login-button")
        self.assertEqual(source, "request_summary")

        fallback_slug, fallback_source = summarize_request_slug("！！！", max_length=40)
        self.assertEqual(fallback_slug, "task")
        self.assertEqual(fallback_source, "fallback_task")


if __name__ == "__main__":
    unittest.main()

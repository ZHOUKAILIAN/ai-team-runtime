import unittest
from pathlib import Path


class DocsTests(unittest.TestCase):
    def test_readmes_document_real_workflow_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        readme_en = (repo_root / "README.md").read_text()
        readme_zh = (repo_root / "README_zh.md").read_text()

        self.assertIn("Product -> CEO approval -> Dev <-> QA -> Acceptance -> human Go/No-Go", readme_en)
        self.assertIn("Product -> CEO 批准 -> Dev <-> QA -> Acceptance -> 人类 Go/No-Go 决策", readme_zh)
        self.assertIn("superpower TDD belongs to Dev", readme_en)
        self.assertIn("superpower TDD 归 Dev", readme_zh)
        self.assertIn("QA must independently rerun critical verification", readme_en)
        self.assertIn("QA 必须独立重跑关键验证", readme_zh)
        self.assertIn("missing evidence forces blocked", readme_en)
        self.assertIn("缺少证据必须 blocked", readme_zh)

    def test_readmes_document_start_session_and_required_artifacts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        readme_en = (repo_root / "README.md").read_text()
        readme_zh = (repo_root / "README_zh.md").read_text()

        self.assertIn("python3 -m ai_company start-session", readme_en)
        self.assertIn("python3 -m ai_company start-session", readme_zh)
        self.assertIn("implementation.md", readme_en)
        self.assertIn("workflow_summary.md", readme_en)
        self.assertIn("implementation.md", readme_zh)
        self.assertIn("workflow_summary.md", readme_zh)

    def test_readmes_label_run_and_agent_run_as_deterministic_demo_runtime(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        readme_en = (repo_root / "README.md").read_text()
        readme_zh = (repo_root / "README_zh.md").read_text()

        self.assertIn("`run` and `agent-run` are deterministic/demo runtime commands", readme_en)
        self.assertIn("`run` 和 `agent-run` 是确定性/演示 runtime 命令", readme_zh)

    def test_skill_documents_single_session_follow_through_rules(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root_skill = (repo_root / "SKILL.md").read_text()

        self.assertIn("start-session", root_skill)
        self.assertIn("Continue after session bootstrap", root_skill)
        self.assertIn("workflow_summary.md", root_skill)
        self.assertIn("implementation.md", root_skill)
        self.assertIn("WaitForCEOApproval", root_skill)
        self.assertIn("WaitForHumanDecision", root_skill)
        self.assertIn("missing evidence forces blocked", root_skill)
        self.assertIn("QA must independently rerun verification", root_skill)


if __name__ == "__main__":
    unittest.main()

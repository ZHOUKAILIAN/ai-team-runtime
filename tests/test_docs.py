import unittest
from pathlib import Path


class DocsTests(unittest.TestCase):
    def test_readmes_document_real_workflow_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        readme_en = (repo_root / "README.md").read_text()
        readme_zh = (repo_root / "README_zh.md").read_text()

        self.assertIn("Product -> CEO approval -> Dev <-> QA -> Acceptance -> human Go/No-Go", readme_en)
        self.assertIn("Product -> CEO 批准 -> Dev <-> QA -> Acceptance -> 人类 Go/No-Go 决策", readme_zh)
        self.assertIn("TDD and any other Dev-only implementation discipline stay inside Dev", readme_en)
        self.assertIn("TDD 以及其他仅属于 Dev 的实现纪律都归 Dev", readme_zh)
        self.assertIn("QA must independently rerun critical verification", readme_en)
        self.assertIn("QA 必须独立重跑关键验证", readme_zh)
        self.assertIn("missing evidence forces blocked", readme_en)
        self.assertIn("缺少证据必须 blocked", readme_zh)
        self.assertNotIn("decides `accepted` or `rejected`", readme_en)
        self.assertNotIn("决定 `accepted` 或 `rejected`", readme_zh)

    def test_readmes_document_skill_first_entrypoints_and_required_artifacts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        readme_en = (repo_root / "README.md").read_text()
        readme_zh = (repo_root / "README_zh.md").read_text()

        self.assertIn("$ai-team-init", readme_en)
        self.assertIn("$ai-team-run", readme_en)
        self.assertIn("project root", readme_en)
        self.assertIn("$ai-team-init", readme_zh)
        self.assertIn("$ai-team-run", readme_zh)
        self.assertIn("项目根目录", readme_zh)
        self.assertIn("prd.md", readme_en)
        self.assertIn("implementation.md", readme_en)
        self.assertIn("qa_report.md", readme_en)
        self.assertIn("acceptance_report.md", readme_en)
        self.assertIn("workflow_summary.md", readme_en)
        self.assertIn("prd.md", readme_zh)
        self.assertIn("implementation.md", readme_zh)
        self.assertIn("qa_report.md", readme_zh)
        self.assertIn("acceptance_report.md", readme_zh)
        self.assertIn("workflow_summary.md", readme_zh)

    def test_readmes_document_project_scoped_codex_setup(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        readme_en = (repo_root / "README.md").read_text()
        readme_zh = (repo_root / "README_zh.md").read_text()

        self.assertIn(".codex/agents/", readme_en)
        self.assertIn(".agents/skills/", readme_en)
        self.assertIn("./scripts/company-init.sh", readme_en)
        self.assertIn("./scripts/company-run.sh", readme_en)
        self.assertIn("$ai-team-run", readme_en)
        self.assertIn(".codex/agents/", readme_zh)
        self.assertIn(".agents/skills/", readme_zh)
        self.assertIn("./scripts/company-init.sh", readme_zh)
        self.assertIn("./scripts/company-run.sh", readme_zh)
        self.assertIn("$ai-team-run", readme_zh)

    def test_readmes_label_run_and_agent_run_as_deterministic_demo_runtime(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        readme_en = (repo_root / "README.md").read_text()
        readme_zh = (repo_root / "README_zh.md").read_text()

        self.assertIn("`run` and `agent-run` are deterministic/demo runtime commands", readme_en)
        self.assertIn("`run` 和 `agent-run` 是确定性/演示 runtime 命令", readme_zh)

    def test_readmes_document_installed_skill_uses_start_session(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        readme_en = (repo_root / "README.md").read_text()
        readme_zh = (repo_root / "README_zh.md").read_text()

        self.assertIn("The installed global skill is the trigger/router layer", readme_en)
        self.assertIn("user-facing entrypoint remains the skill itself", readme_en)
        self.assertNotIn("The actual execution still runs through:\n\n```bash\npython3 -m ai_company agent-run", readme_en)
        self.assertIn("这个全局 skill 的职责是触发和路由", readme_zh)
        self.assertIn("对用户来说，入口仍然是 skill 本身", readme_zh)
        self.assertNotIn("真正执行仍然会落到仓库里的：\n\n```bash\npython3 -m ai_company agent-run", readme_zh)

    def test_skill_documents_single_session_follow_through_rules(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root_skill = (repo_root / "SKILL.md").read_text()
        qa_skill = (repo_root / "QA" / "SKILL.md").read_text()
        acceptance_skill = (repo_root / "Acceptance" / "SKILL.md").read_text()
        dev_skill = (repo_root / "Dev" / "SKILL.md").read_text()
        product_skill = (repo_root / "Product" / "SKILL.md").read_text()
        project_init_skill = (repo_root / ".agents" / "skills" / "ai-team-init" / "SKILL.md").read_text()
        project_run_skill = (repo_root / ".agents" / "skills" / "ai-team-run" / "SKILL.md").read_text()

        self.assertIn("start-session", root_skill)
        self.assertIn("Continue after session bootstrap", root_skill)
        self.assertIn("workflow_summary.md", root_skill)
        self.assertIn("implementation.md", root_skill)
        self.assertIn("WaitForCEOApproval", root_skill)
        self.assertIn("WaitForHumanDecision", root_skill)
        self.assertIn("missing evidence forces blocked", root_skill)
        self.assertIn("QA must independently rerun verification", root_skill)
        self.assertIn(".codex/agents/*.toml", root_skill)
        self.assertIn("./scripts/company-run.sh", root_skill)
        self.assertIn("session_id", product_skill)
        self.assertIn("waiting for CEO approval", product_skill)
        self.assertIn("implementation.md", dev_skill)
        self.assertNotIn("dev_notes.md", dev_skill)
        self.assertIn("Use rigorous engineering discipline inside Dev.", dev_skill)
        self.assertIn("already specified the verification platform", qa_skill)
        self.assertIn("session_id", qa_skill)
        self.assertIn("implementation.md", qa_skill)
        self.assertIn("miniprogram", qa_skill)
        self.assertIn("browser-use", qa_skill)
        self.assertIn("already specified the verification platform", acceptance_skill)
        self.assertIn("recommended_go", acceptance_skill)
        self.assertIn("recommended_no_go", acceptance_skill)
        self.assertIn("miniprogram", acceptance_skill)
        self.assertIn("browser-use", acceptance_skill)
        self.assertIn("project's root directory", project_init_skill)
        self.assertIn("$ai-team-run", project_init_skill)
        self.assertIn(".codex/agents/", project_run_skill)
        self.assertIn("root directory", project_run_skill)
        self.assertIn("./scripts/company-run.sh", project_run_skill)
        self.assertIn("workflow_summary.md", project_run_skill)


if __name__ == "__main__":
    unittest.main()

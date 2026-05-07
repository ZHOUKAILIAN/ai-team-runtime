import unittest
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class RuntimeDriverSchemaTests(unittest.TestCase):
    def test_stage_result_schema_is_strict_for_codex_structured_output(self) -> None:
        from agent_team.runtime_driver import _stage_result_schema

        def assert_strict_objects(schema: dict[str, object], path: str) -> None:
            if schema.get("type") == "object":
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                self.assertEqual(schema.get("additionalProperties"), False, path)
                for name in required:
                    self.assertIn(name, properties, f"{path}: {name} in required but not properties")
                for name, child in properties.items():
                    if isinstance(child, dict):
                        assert_strict_objects(child, f"{path}.{name}")
            if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
                assert_strict_objects(schema["items"], f"{path}[]")

        assert_strict_objects(_stage_result_schema(), "$")

    def test_stage_result_schema_excludes_runtime_control_fields(self) -> None:
        from agent_team.runtime_driver import _stage_result_schema
        from agent_team.stage_payload import FORBIDDEN_STAGE_PAYLOAD_FIELDS

        properties = _stage_result_schema()["properties"]

        for field in FORBIDDEN_STAGE_PAYLOAD_FIELDS:
            self.assertNotIn(field, properties)
        self.assertNotIn("supplemental_artifacts", properties)

    def test_codex_prompt_instructs_product_prd_chinese_without_non_goals(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import Finding, StageContract
        from agent_team.runtime_driver import StageExecutionRequest, _build_codex_prompt

        request = StageExecutionRequest(
            repo_root=Path("/repo"),
            state_store=None,
            session_id="session",
            run_id="product-run-1",
            contract=StageContract(
                session_id="session",
                stage="Product",
                goal="Write PRD",
                contract_id="contract",
                required_outputs=["product-requirements.md"],
            ),
            context=StageExecutionContext(
                session_id="session",
                stage="Product",
                round_index=1,
                context_id="context",
                contract_id="contract",
                original_request_summary="写个js文件，并打印hello world",
                approved_prd_summary="",
                acceptance_matrix=[],
                constraints=[],
                required_outputs=["product-requirements.md"],
                required_evidence=[],
                relevant_artifacts=[],
                actionable_findings=[
                    Finding(
                        source_stage="Product",
                        target_stage="Product",
                        issue="在桌面生成文件",
                    )
                ],
            ),
            contract_path=Path("/tmp/contract.json"),
            context_path=Path("/tmp/context.json"),
            result_path=Path("/tmp/result.json"),
            output_schema_path=Path("/tmp/schema.json"),
        )

        prompt = _build_codex_prompt(request)

        self.assertIn("Write artifact_content primarily in Chinese", prompt)
        self.assertIn("acceptance_plan_content is acceptance_plan.md", prompt)
        self.assertIn("需求背景", prompt)
        self.assertIn("<human_revision_requests>", prompt)
        self.assertIn("product-requirements.md must contain a clear Markdown link to `acceptance_plan.md`", prompt)
        self.assertIn("acceptance_plan.md must begin with a clear Markdown link back to `product-requirements.md`", prompt)
        self.assertIn("在桌面生成文件", prompt)
        self.assertIn("fold them into the PRD's goals", prompt)
        self.assertNotIn("Non-Goals", prompt)
        self.assertNotIn("非目标", prompt)

    def test_codex_prompt_instructs_dev_technical_plan_tables_and_flowcharts(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import StageContract
        from agent_team.runtime_driver import StageExecutionRequest, _build_codex_prompt

        request = StageExecutionRequest(
            repo_root=Path("/repo"),
            state_store=None,
            session_id="session",
            run_id="dev-run-1",
            contract=StageContract(
                session_id="session",
                stage="Dev",
                goal="Write technical plan",
                contract_id="contract",
                required_outputs=["technical_plan.md"],
            ),
            context=StageExecutionContext(
                session_id="session",
                stage="Dev",
                round_index=1,
                context_id="context",
                contract_id="contract",
                original_request_summary="写个js文件，并打印hello world",
                approved_prd_summary="# 需求方案",
                acceptance_matrix=[],
                constraints=[],
                required_outputs=["technical_plan.md"],
                required_evidence=[],
                relevant_artifacts=[],
            ),
            contract_path=Path("/tmp/contract.json"),
            context_path=Path("/tmp/context.json"),
            result_path=Path("/tmp/result.json"),
            output_schema_path=Path("/tmp/schema.json"),
        )

        prompt = _build_codex_prompt(request)

        self.assertIn("You are Dev, but this pass is only the technical plan approval step", prompt)
        self.assertIn("Write artifact_content as technical_plan.md", prompt)
        self.assertIn("Do not edit repository source code", prompt)
        self.assertIn("Prefer Mermaid flowcharts", prompt)
        self.assertIn("Markdown tables", prompt)
        self.assertIn("Avoid bullet lists", prompt)
        self.assertNotIn("Non-Goals", prompt)
        self.assertNotIn("非目标", prompt)

    def test_codex_prompt_instructs_dev_to_follow_approved_tech_plan_content(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import StageContract
        from agent_team.runtime_driver import StageExecutionRequest, _build_codex_prompt

        request = StageExecutionRequest(
            repo_root=Path("/repo"),
            state_store=None,
            session_id="session",
            run_id="dev-run-1",
            contract=StageContract(
                session_id="session",
                stage="Dev",
                goal="Implement",
                contract_id="contract",
                required_outputs=["implementation.md"],
            ),
            context=StageExecutionContext(
                session_id="session",
                stage="Dev",
                round_index=1,
                context_id="context",
                contract_id="contract",
                original_request_summary="写个js文件，并打印hello world",
                approved_prd_summary="# 需求方案",
                acceptance_matrix=[],
                constraints=[],
                required_outputs=["implementation.md"],
                required_evidence=[],
                relevant_artifacts=[],
                approved_tech_plan_content="# 技术方案\n\n- 按已确认技术方案创建 hello.js。\n",
            ),
            contract_path=Path("/tmp/contract.json"),
            context_path=Path("/tmp/context.json"),
            result_path=Path("/tmp/result.json"),
            output_schema_path=Path("/tmp/schema.json"),
        )

        prompt = _build_codex_prompt(request)

        self.assertIn("Treat StageExecutionContext.approved_tech_plan_content as the approved implementation plan", prompt)
        self.assertIn("按已确认技术方案创建 hello.js", prompt)

    def test_codex_prompt_includes_enabled_skills(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import StageContract
        from agent_team.runtime_driver import StageExecutionRequest, _build_codex_prompt
        from agent_team.skill_registry import Skill

        request = StageExecutionRequest(
            repo_root=Path("/repo"),
            state_store=None,
            session_id="session",
            run_id="dev-run-1",
            contract=StageContract(
                session_id="session",
                stage="Dev",
                goal="Implement",
                contract_id="contract",
                required_outputs=["implementation.md"],
            ),
            context=StageExecutionContext(
                session_id="session",
                stage="Dev",
                round_index=1,
                context_id="context",
                contract_id="contract",
                original_request_summary="写个js文件，并打印hello world",
                approved_prd_summary="# 需求方案",
                acceptance_matrix=[],
                constraints=[],
                required_outputs=["implementation.md"],
                required_evidence=[],
                relevant_artifacts=[],
                approved_tech_plan_content="# 技术方案\n\n- 按已确认技术方案创建 hello.js。\n",
            ),
            contract_path=Path("/tmp/contract.json"),
            context_path=Path("/tmp/context.json"),
            result_path=Path("/tmp/result.json"),
            output_schema_path=Path("/tmp/schema.json"),
            skill_asset_root=Path(
                "/repo/.agent-team/_runtime/sessions/session/roles/dev/attempt-001/execution-contexts/skills/.agent-team/skills"
            ),
            skills=[
                Skill(
                    name="plan",
                    description="Plan the implementation",
                    content="# Plan\n\nDo the plan.",
                    source="builtin",
                    path=Path("/skills/plan/SKILL.md"),
                    source_ref="https://example.com/skills/plan",
                    stages=("Dev",),
                    delivery="sandbox",
                )
            ],
        )

        prompt = _build_codex_prompt(request)

        self.assertIn("<enabled_skills>", prompt)
        self.assertIn('<skill name="plan">', prompt)
        self.assertIn("<source_type>builtin</source_type>", prompt)
        self.assertIn("<source_ref>https://example.com/skills/plan</source_ref>", prompt)
        self.assertIn(
            "<asset_root>/repo/.agent-team/_runtime/sessions/session/roles/dev/attempt-001/execution-contexts/skills/.agent-team/skills/plan/</asset_root>",
            prompt,
        )
        self.assertIn("Do the plan", prompt)

    def test_dry_run_product_artifact_omits_non_goals(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import Finding
        from agent_team.runtime_driver import _dry_run_artifact_content, _dry_run_supplemental_artifacts

        context = StageExecutionContext(
            session_id="session",
            stage="Product",
            round_index=1,
            context_id="context",
            contract_id="contract",
            original_request_summary="写个js文件，并打印hello world",
            approved_prd_summary="",
            acceptance_matrix=[],
            constraints=[],
            required_outputs=["product-requirements.md"],
            required_evidence=[],
            relevant_artifacts=[],
            actionable_findings=[
                Finding(
                    source_stage="Product",
                    target_stage="Product",
                    issue="在桌面生成文件",
                )
            ],
        )

        artifact = _dry_run_artifact_content("Product", context)

        self.assertIn("# 需求方案", artifact)
        self.assertIn("人工修改意见", artifact)
        self.assertIn("在桌面生成文件", artifact)
        self.assertNotIn("Non-Goals", artifact)
        self.assertNotIn("非目标", artifact)
        supplemental = _dry_run_supplemental_artifacts("Product", context)
        self.assertIn("acceptance_plan.md", supplemental)
        self.assertIn("数据库", supplemental["acceptance_plan.md"])

    def test_codex_exec_stage_executor_skips_git_repo_check(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import StageContract
        from agent_team.runtime_driver import CodexExecStageExecutor, RuntimeDriverOptions, StageExecutionRequest

        commands = []

        def fake_run(command, *, cwd, capture_output, text, timeout, check, env=None, stdin=None):
            commands.append(command)
            output_path = Path(command[command.index("-o") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "artifact_content": "# PRD\n",
                        "journal": "",
                        "findings": [],
                        "evidence": [],
                        "suggested_next_owner": "",
                        "summary": "Product completed.",
                        "acceptance_status": "",
                        "acceptance_plan_content": "",
                        "blocked_reason": "",
                    }
                )
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            request = StageExecutionRequest(
                repo_root=root,
                state_store=None,
                session_id="session",
                run_id="product-run-1",
                contract=StageContract(
                    session_id="session",
                    stage="Product",
                    goal="Write a PRD.",
                    contract_id="contract",
                    required_outputs=["product-requirements.md"],
                ),
                context=StageExecutionContext(
                    session_id="session",
                    stage="Product",
                    round_index=1,
                    context_id="context",
                    contract_id="contract",
                    original_request_summary="写个js文件，并打印hello world",
                    approved_prd_summary="",
                    acceptance_matrix=[],
                    constraints=[],
                    required_outputs=["product-requirements.md"],
                    required_evidence=[],
                    relevant_artifacts=[],
                ),
                contract_path=root / "contract.json",
                context_path=root / "context.json",
                result_path=root / "result.json",
                output_schema_path=root / "schema.json",
                prompt_path=root / "prompt.md",
            )

            with patch("agent_team.runtime_driver.subprocess.run", fake_run):
                envelope = CodexExecStageExecutor(RuntimeDriverOptions()).execute(request)

        self.assertEqual(len(commands), 1)
        self.assertIn("--skip-git-repo-check", commands[0])
        self.assertEqual(envelope.session_id, "session")
        self.assertEqual(envelope.stage, "Product")
        self.assertEqual(envelope.contract_id, "contract")
        self.assertEqual(envelope.artifact_name, "product-requirements.md")

    def test_stage_payload_parser_rejects_runtime_control_fields(self) -> None:
        from agent_team.runtime_driver import _stage_result_from_json_text

        request = SimpleNamespace(
            session_id="runtime-session",
            contract=SimpleNamespace(stage="Product", contract_id="runtime-contract"),
        )
        result = _stage_result_from_json_text(
            request=request,
            value=json.dumps(
                {
                    "stage": "Product",
                    "status": "completed",
                    "artifact_content": "# PRD\n",
                    "journal": "",
                    "findings": [],
                    "evidence": [],
                    "suggested_next_owner": "",
                    "summary": "done",
                    "acceptance_status": "",
                    "acceptance_plan_content": "",
                    "blocked_reason": "",
                }
            ),
            source="stdout",
        )

        self.assertEqual(result.status, "blocked")
        self.assertIn("runtime-controlled field(s): stage", result.blocked_reason)

    def test_stage_run_streams_accept_timeout_bytes(self) -> None:
        from agent_team.runtime_driver import _write_stage_run_streams

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            request = SimpleNamespace(
                result_path=Path(temp_dir) / "stage_runs" / "product-run-1_result.json",
                run_id="product-run-1",
            )
            _write_stage_run_streams(request, stdout=b"partial stdout", stderr=b"partial stderr")

            stdout = (Path(temp_dir) / "stage_runs" / "product-run-1_stdout.txt").read_text()
            stderr = (Path(temp_dir) / "stage_runs" / "product-run-1_stderr.txt").read_text()

        self.assertEqual(stdout, "partial stdout")
        self.assertEqual(stderr, "partial stderr")


class RuntimeDriverTraceTests(unittest.TestCase):
    def test_dry_run_records_non_skippable_stage_trace(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "run",
                    "--message",
                    "执行这个需求：验证 runtime trace 不允许跳过链路步骤",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            session_id = dict(
                line.split(": ", 1) for line in result.stdout.splitlines() if ": " in line
            )["session_id"]
            stage_result_path = (
                Path(temp_dir)
                / "_runtime"
                / "sessions"
                / session_id
                / "roles"
                / "product"
                / "attempt-001"
                / "stage-results"
                / "product-stage-result.json"
            )
            stage_result = json.loads(stage_result_path.read_text())

        self.assertEqual(
            [step["step"] for step in stage_result["steps"]],
            [
                "contract_built",
                "execution_context_built",
                "stage_run_acquired",
                "executor_started",
                "executor_completed",
                "result_submitted",
                "gate_evaluated",
                "state_advanced",
            ],
        )
        self.assertTrue(all(step["status"] == "ok" for step in stage_result["steps"]))
        self.assertIn("stage_result", stage_result)
        self.assertNotIn("artifact_content", stage_result["stage_result"])
        self.assertNotIn("supplemental_artifacts", stage_result["stage_result"])
        self.assertIn("supplemental_artifact_paths", stage_result["stage_result"])
        self.assertFalse(
            (
                Path(temp_dir)
                / "_runtime"
                / "sessions"
                / session_id
                / "roles"
                / "product"
                / "attempt-001"
                / "stage-results"
                / "product-run-state.json"
            ).exists()
        )
        self.assertFalse(
            (
                Path(temp_dir)
                / "_runtime"
                / "sessions"
                / session_id
                / "roles"
                / "product"
                / "attempt-001"
                / "stage-results"
                / "product-runtime-trace.json"
            ).exists()
        )
        self.assertFalse(
            (
                Path(temp_dir)
                / "_runtime"
                / "sessions"
                / session_id
                / "roles"
                / "product"
                / "attempt-001"
                / "execution-contexts"
                / "product-agent-prompt-bundle.md"
            ).exists()
        )

    def test_runtime_trace_validator_blocks_missing_required_steps(self) -> None:
        from agent_team.runtime_driver import REQUIRED_PASS_TRACE_STEPS, _validate_runtime_trace

        trace = [{"step": step, "status": "ok"} for step in REQUIRED_PASS_TRACE_STEPS[:-1]]
        result = _validate_runtime_trace(trace, required_steps=REQUIRED_PASS_TRACE_STEPS)

        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("state_advanced", result.reason)


class RuntimeDriverInteractiveFlowTests(unittest.TestCase):
    def test_interactive_dry_run_stops_at_tech_plan_approval_after_product_go(self) -> None:
        from agent_team.runtime_driver import RuntimeDriverOptions, run_requirement
        from agent_team.stage_machine import StageMachine
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir)
            product_result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                message="执行这个需求：写个js文件，并打印hello world",
                options=RuntimeDriverOptions(
                    executor="dry-run",
                    interactive=True,
                ),
            )
            store = StateStore(state_root)
            session = store.load_session(product_result.session_id)
            summary = store.load_workflow_summary(product_result.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))
            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=product_result.session_id,
                options=RuntimeDriverOptions(
                    executor="dry-run",
                    interactive=True,
                ),
            )

            self.assertEqual(result.status, "waiting_human")
            self.assertEqual(result.current_state, "WaitForTechnicalPlanApproval")
            self.assertEqual(result.current_stage, "Dev")
            self.assertEqual(result.stage_run_count, 1)
            session_dir = Path(temp_dir) / result.session_id
            self.assertTrue((session_dir / "product-requirements.md").exists())
            self.assertTrue((session_dir / "acceptance_plan.md").exists())
            self.assertTrue((session_dir / "technical_plan.md").exists())

    def test_auto_advance_intermediate_stops_at_final_acceptance_gate(self) -> None:
        from agent_team.runtime_driver import RuntimeDriverOptions, run_requirement
        from agent_team.stage_machine import StageMachine
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir)
            product_result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                message="执行这个需求：写个js文件，并打印hello world",
                options=RuntimeDriverOptions(
                    executor="dry-run",
                    interactive=True,
                ),
            )
            store = StateStore(state_root)
            session = store.load_session(product_result.session_id)
            summary = store.load_workflow_summary(product_result.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))
            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=product_result.session_id,
                options=RuntimeDriverOptions(
                    executor="dry-run",
                    interactive=True,
                    auto_advance_intermediate=True,
                ),
            )

            self.assertEqual(result.status, "waiting_human")
            self.assertEqual(result.current_state, "WaitForTechnicalPlanApproval")
            self.assertEqual(result.current_stage, "Dev")
            self.assertEqual(result.stage_run_count, 1)
            summary = store.load_workflow_summary(product_result.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))

            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=product_result.session_id,
                options=RuntimeDriverOptions(
                    executor="dry-run",
                    interactive=True,
                    auto_advance_intermediate=True,
                ),
            )

            self.assertEqual(result.status, "waiting_human")
            self.assertEqual(result.current_state, "WaitForHumanDecision")
            self.assertEqual(result.current_stage, "Acceptance")
            self.assertEqual(result.stage_run_count, 3)
            session_dir = Path(temp_dir) / result.session_id
            self.assertTrue((session_dir / "product-requirements.md").exists())
            self.assertTrue((session_dir / "acceptance_plan.md").exists())
            self.assertTrue((session_dir / "technical_plan.md").exists())
            self.assertTrue((session_dir / "implementation.md").exists())
            self.assertTrue((session_dir / "qa_report.md").exists())
            self.assertTrue((session_dir / "acceptance_report.md").exists())

    def test_interactive_driver_blocks_invalid_stage_identity_without_traceback(self) -> None:
        from agent_team.runtime_driver import RuntimeDriverOptions, run_requirement
        from agent_team.stage_machine import StageMachine
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            worker_path = Path(temp_dir) / "bad_stage_worker.py"
            worker_path.write_text(
                "import json, os\n"
                "stage = os.environ['AGENT_TEAM_STAGE']\n"
                "contract = json.loads(open(os.environ['AGENT_TEAM_CONTRACT_PATH']).read())\n"
                "technical_plan = stage == 'Dev' and 'technical_plan.md' in contract.get('required_outputs', [])\n"
                "payload = {\n"
                "    'status': 'completed',\n"
                "    'artifact_content': '# Technical Plan\\n' if technical_plan else '# PRD\\n\\n## Acceptance Plan\\n- [Acceptance Plan](acceptance_plan.md)\\n',\n"
                "    'acceptance_plan_content': '' if technical_plan else '# Acceptance Plan\\n\\n## Requirements\\n- [PRD](product-requirements.md)\\n\\n## Verification\\n- Exercise the product path.\\n',\n"
                "    'journal': '',\n"
                "    'findings': [],\n"
                "    'evidence': [\n"
                "        {\n"
                "            'name': 'implementation_plan' if technical_plan else 'explicit_acceptance_plan',\n"
                "            'kind': 'report',\n"
                "            'summary': 'Evidence provided.',\n"
                "        }\n"
                "    ],\n"
                "    'suggested_next_owner': '',\n"
                "    'summary': 'done',\n"
                "    'acceptance_status': '',\n"
                "    'blocked_reason': '',\n"
                "}\n"
                "if technical_plan:\n"
                "    payload['stage'] = 'Product'\n"
                "open(os.environ['AGENT_TEAM_RESULT_BUNDLE'], 'w').write(json.dumps(payload))\n"
            )

            state_root = Path(temp_dir)
            product_result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                message="执行这个需求：写个js文件，并打印hello world",
                options=RuntimeDriverOptions(
                    executor="command",
                    executor_command=f"{sys.executable} {worker_path}",
                    interactive=True,
                ),
            )
            store = StateStore(state_root)
            session = store.load_session(product_result.session_id)
            summary = store.load_workflow_summary(product_result.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))
            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=product_result.session_id,
                options=RuntimeDriverOptions(
                    executor="command",
                    executor_command=f"{sys.executable} {worker_path}",
                    interactive=True,
                ),
            )
            summary = store.load_workflow_summary(result.session_id)
            run = store.latest_stage_run(result.session_id, stage="Dev")

            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.current_state, "Dev")
            self.assertIn("Invalid stage payload JSON", result.gate_reason)
            self.assertIn("runtime-controlled field(s): stage", result.gate_reason)
            self.assertEqual(summary.blocked_reason, result.gate_reason)
            self.assertIsNotNone(run)
            self.assertEqual(run.state, "BLOCKED")


if __name__ == "__main__":
    unittest.main()

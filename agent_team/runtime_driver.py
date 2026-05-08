from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .codex_isolation import isolated_codex_env
from .execution_context import StageExecutionContext, build_stage_execution_context
from .gate_evaluator import GateEvaluator, NoopJudge
from .gatekeeper import evaluate_candidate
from .intake import parse_intake_message
from .models import EvidenceItem, Finding, GateResult, StageContract, StageResultEnvelope, WorkflowSummary
from .openai_sandbox_judge import OpenAISandboxJudge, OpenAISandboxJudgeUnavailable
from .stage_contracts import build_stage_contract
from .stage_machine import StageMachine
from .stage_payload import envelope_from_stage_payload
from .stage_policies import default_policy_registry
from .state import StageRunStateError, StateStore, artifact_name_for_stage
from .skill_registry import Skill, skill_injection_text, skill_scope
from .workflow import EXECUTABLE_STATES, artifact_key_for


REQUIRED_PASS_TRACE_STEPS = [
    "contract_built",
    "execution_context_built",
    "stage_run_acquired",
    "executor_started",
    "executor_completed",
    "result_submitted",
    "gate_evaluated",
    "state_advanced",
]


@dataclass(slots=True)
class RuntimeDriverOptions:
    executor: str = "codex-exec"
    executor_command: str = ""
    command_timeout_seconds: int = 3600
    auto_advance_intermediate: bool = False
    max_stage_runs: int = 12
    judge: str = "off"
    model: str = "gpt-5.4"
    docker_image: str = "python:3.13-slim"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_proxy_url: str | None = None
    openai_user_agent: str = "Agent-Team-Runtime/0.1"
    openai_oa: str | None = None
    codex_model: str = ""
    codex_sandbox: str = "workspace-write"
    codex_approval_policy: str = "never"
    codex_extra_args: list[str] = field(default_factory=list)
    enabled_skills_by_stage: dict[str, list[Skill]] = field(default_factory=dict)
    codex_isolate_home: bool = True
    codex_ignore_rules: bool = True
    codex_disable_plugins: bool = True
    codex_ephemeral: bool = True
    codex_skip_git_repo_check: bool = True
    interactive: bool = False
    trace_prompts: bool = False


@dataclass(slots=True)
class RuntimeDriverResult:
    session_id: str
    artifact_dir: Path
    summary_path: Path
    status: str
    current_state: str
    current_stage: str
    acceptance_status: str
    human_decision: str
    next_action: str = ""
    stage_run_count: int = 0
    gate_status: str = ""
    gate_reason: str = ""


@dataclass(slots=True)
class StageExecutionRequest:
    repo_root: Path
    state_store: StateStore
    session_id: str
    run_id: str
    contract: StageContract
    context: StageExecutionContext
    contract_path: Path
    context_path: Path
    result_path: Path
    output_schema_path: Path
    prompt_path: Path | None = None
    skill_asset_root: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    skills: list[Skill] = field(default_factory=list)


class RuntimeDriverError(RuntimeError):
    pass


class StageExecutor(Protocol):
    name: str

    def execute(self, request: StageExecutionRequest) -> StageResultEnvelope:
        raise NotImplementedError


def _write_stage_run_streams(request: StageExecutionRequest, *, stdout: object, stderr: object) -> None:
    request.result_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = getattr(request, "stdout_path", None) or request.result_path.parent / f"{request.run_id}_stdout.txt"
    stderr_path = getattr(request, "stderr_path", None) or request.result_path.parent / f"{request.run_id}_stderr.txt"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(_coerce_stream_text(stdout))
    stderr_path.write_text(_coerce_stream_text(stderr))


def _skill_trace_entry(skill: Skill, skill_asset_root: Path, included_in_prompt: bool) -> dict[str, Any]:
    installed_path = skill_asset_root / skill.name
    return {
        "name": skill.name,
        "description": skill.description,
        "source": skill.source,
        "source_ref": skill.source_ref or str(skill.path.parent.resolve()),
        "scope": skill_scope(skill.source),
        "path": str(skill.path),
        "stages": list(skill.stages),
        "delivery": skill.delivery,
        "included_in_prompt": included_in_prompt,
        "installed_path": str(installed_path) if skill.delivery == "sandbox" else "",
        "sandbox_files": list(skill.sandbox_files),
        "env_vars": list(skill.env_vars),
    }


def _install_runtime_sandbox_skills(skills: list[Skill], skill_asset_root: Path) -> None:
    for skill in skills:
        if skill.delivery != "sandbox":
            continue
        destination = skill_asset_root / skill.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(skill.path.parent, destination)


def _coerce_stream_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_requirement(
    *,
    repo_root: Path,
    state_root: Path,
    message: str = "",
    session_id: str = "",
    options: RuntimeDriverOptions | None = None,
) -> RuntimeDriverResult:
    opts = options or RuntimeDriverOptions()
    store = StateStore(state_root)
    store.ensure_layout()
    session = store.load_session(session_id) if session_id else _create_driver_session(
        store,
        message,
        interactive=opts.interactive,
    )
    if opts.interactive:
        _ensure_interactive_runtime_mode(store=store, session_id=session.session_id)
    executor = build_stage_executor(opts)

    stage_run_count = 0
    while True:
        summary = store.load_workflow_summary(session.session_id)
        waiting = _handle_wait_state(
            repo_root=repo_root,
            store=store,
            summary=summary,
            auto_advance_intermediate=opts.auto_advance_intermediate,
        )
        if waiting is not None:
            return _result_from_summary(
                store=store,
                session_id=session.session_id,
                status=waiting[0],
                next_action=waiting[1],
                stage_run_count=stage_run_count,
            )

        summary = store.load_workflow_summary(session.session_id)
        stage = _expected_submission_stage(summary)
        if stage is None:
            status = "done" if summary.current_state == "Done" else "idle"
            return _result_from_summary(
                store=store,
                session_id=session.session_id,
                status=status,
                stage_run_count=stage_run_count,
            )
        if stage_run_count >= opts.max_stage_runs:
            return _result_from_summary(
                store=store,
                session_id=session.session_id,
                status="blocked",
                next_action="increase --max-stage-runs or inspect the active findings",
                stage_run_count=stage_run_count,
                gate_status="BLOCKED",
                gate_reason=f"Runtime driver reached max_stage_runs={opts.max_stage_runs}.",
            )

        gate_result = _execute_stage(
            repo_root=repo_root,
            store=store,
            session_id=session.session_id,
            stage=stage,
            executor=executor,
            options=opts,
        )
        stage_run_count += 1
        if gate_result.status != "PASSED":
            return _result_from_summary(
                store=store,
                session_id=session.session_id,
                status=gate_result.status.lower(),
                stage_run_count=stage_run_count,
                gate_status=gate_result.status,
                gate_reason=gate_result.reason,
            )


def build_stage_executor(options: RuntimeDriverOptions) -> StageExecutor:
    if options.executor == "dry-run":
        return DryRunStageExecutor()
    if options.executor == "command":
        if not options.executor_command.strip():
            raise RuntimeDriverError("--executor-command is required when --executor command is used.")
        return CommandStageExecutor(
            command=options.executor_command,
            timeout_seconds=options.command_timeout_seconds,
        )
    if options.executor == "codex-exec":
        return CodexExecStageExecutor(options)
    raise RuntimeDriverError(f"Unsupported runtime driver executor: {options.executor}")


class DryRunStageExecutor:
    name = "dry-run"

    def execute(self, request: StageExecutionRequest) -> StageResultEnvelope:
        stage = request.contract.stage
        artifact_name = _contract_artifact_name(request.contract)
        return StageResultEnvelope(
            session_id=request.session_id,
            stage=stage,
            status="completed",
            artifact_name=artifact_name,
            artifact_content=_dry_run_artifact_content(stage, request.context, artifact_name=artifact_name),
            contract_id=request.contract.contract_id,
            journal=f"Dry-run executor produced {artifact_name} for {stage}.",
            evidence=_default_evidence(stage, artifact_name=artifact_name),
            summary=f"{stage} dry-run result satisfied the stage contract.",
            acceptance_status="recommended_go" if stage == "Acceptance" else "",
            supplemental_artifacts=_dry_run_supplemental_artifacts(stage, request.context),
        )


class CommandStageExecutor:
    name = "command"

    def __init__(self, *, command: str, timeout_seconds: int) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

    def execute(self, request: StageExecutionRequest) -> StageResultEnvelope:
        request.result_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(_stage_environment(request))
        try:
            completed = subprocess.run(
                self.command,
                cwd=request.repo_root,
                env=env,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _coerce_stream_text(exc.stdout)
            stderr = _coerce_stream_text(exc.stderr) or f"Executor timed out after {self.timeout_seconds} seconds."
            _write_stage_run_streams(
                request,
                stdout=stdout,
                stderr=stderr,
            )
            return _blocked_result_from_process(
                request=request,
                command=self.command,
                stdout=stdout,
                stderr=stderr,
                exit_code=124,
            )
        _write_stage_run_streams(request, stdout=completed.stdout, stderr=completed.stderr)
        if request.result_path.exists():
            return _stage_result_from_json_text(
                request=request,
                value=request.result_path.read_text(),
                source=str(request.result_path),
            )
        if completed.stdout.strip():
            return _stage_result_from_json_text(request=request, value=completed.stdout, source="stdout")
        return _blocked_result_from_process(
            request=request,
            command=self.command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )


class CodexExecStageExecutor:
    name = "codex-exec"

    def __init__(self, options: RuntimeDriverOptions) -> None:
        self.options = options

    def execute(self, request: StageExecutionRequest) -> StageResultEnvelope:
        request.result_path.parent.mkdir(parents=True, exist_ok=True)
        prompt = _build_codex_prompt(request)
        if request.prompt_path is not None:
            request.prompt_path.parent.mkdir(parents=True, exist_ok=True)
            request.prompt_path.write_text(prompt)
        command = [
            "codex",
            "exec",
            "--cd",
            str(request.repo_root),
            "--sandbox",
            self.options.codex_sandbox,
            "-c",
            f'approval_policy="{self.options.codex_approval_policy}"',
            "--output-schema",
            str(request.output_schema_path),
            "-o",
            str(request.result_path),
        ]
        if self.options.codex_ignore_rules:
            command.append("--ignore-rules")
        if self.options.codex_disable_plugins:
            command.extend(["--disable", "plugins"])
        if self.options.codex_ephemeral:
            command.append("--ephemeral")
        if self.options.codex_skip_git_repo_check:
            command.append("--skip-git-repo-check")
        if self.options.codex_model:
            command.extend(["--model", self.options.codex_model])
        command.extend(self.options.codex_extra_args)
        command.append(prompt)
        try:
            if self.options.codex_isolate_home:
                with isolated_codex_env() as env:
                    completed = subprocess.run(
                        command,
                        cwd=request.repo_root,
                        capture_output=True,
                        text=True,
                        timeout=self.options.command_timeout_seconds,
                        check=False,
                        env=env,
                        stdin=subprocess.DEVNULL,
                    )
            else:
                completed = subprocess.run(
                    command,
                    cwd=request.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=self.options.command_timeout_seconds,
                    check=False,
                    stdin=subprocess.DEVNULL,
                )
        except FileNotFoundError as exc:
            _write_stage_run_streams(request, stdout="", stderr=str(exc))
            return _blocked_result_from_process(
                request=request,
                command="codex exec",
                stdout="",
                stderr=str(exc),
                exit_code=127,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _coerce_stream_text(exc.stdout)
            stderr = _coerce_stream_text(exc.stderr) or f"codex exec timed out after {self.options.command_timeout_seconds} seconds."
            _write_stage_run_streams(
                request,
                stdout=stdout,
                stderr=stderr,
            )
            return _blocked_result_from_process(
                request=request,
                command="codex exec",
                stdout=stdout,
                stderr=stderr,
                exit_code=124,
            )
        _write_stage_run_streams(request, stdout=completed.stdout, stderr=completed.stderr)
        if completed.returncode != 0 and not request.result_path.exists():
            return _blocked_result_from_process(
                request=request,
                command=" ".join(command[:2]),
                stdout=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.returncode,
            )
        if not request.result_path.exists():
            raise RuntimeDriverError("codex exec completed without writing the stage result file.")
        return _stage_result_from_json_text(
            request=request,
            value=request.result_path.read_text(),
            source=str(request.result_path),
        )


def _create_driver_session(store: StateStore, message: str, *, interactive: bool = False):
    intake = parse_intake_message(message)
    if not intake.request:
        raise RuntimeDriverError("Unable to extract a workflow request from --message.")
    return store.create_session(
        intake.request,
        raw_message=message,
        contract=intake.contract,
        runtime_mode="runtime_driver_interactive" if interactive else "runtime_driver",
        initiator="human",
    )


def _ensure_interactive_runtime_mode(*, store: StateStore, session_id: str) -> None:
    session = store.load_session(session_id)
    summary = store.load_workflow_summary(session_id)
    if summary.runtime_mode == "runtime_driver_interactive":
        return
    store.save_workflow_summary(session, replace(summary, runtime_mode="runtime_driver_interactive"))


def _handle_wait_state(
    *,
    repo_root: Path,
    store: StateStore,
    summary: WorkflowSummary,
    auto_advance_intermediate: bool,
) -> tuple[str, str] | None:
    del repo_root
    if summary.current_state == "WaitForProductDefinitionApproval":
        if summary.runtime_mode == "runtime_driver_interactive":
            return ("waiting_human", "record-human-decision --decision go|rework|no-go")
        return ("waiting_human", "record-human-decision --decision go")
    if summary.current_state == "WaitForTechnicalDesignApproval":
        return ("waiting_human", "record-human-decision --decision go|rework|no-go")
    if summary.current_state == "WaitForHumanDecision":
        return ("waiting_human", "record-human-decision --decision go|no-go|rework")
    if summary.current_state == "Blocked":
        return ("blocked", "inspect gate_reason and route rework")
    return None


def _apply_human_decision(*, store: StateStore, summary: WorkflowSummary, decision: str) -> None:
    session = store.load_session(summary.session_id)
    updated = StageMachine().apply_human_decision(summary=summary, decision=decision)
    store.save_workflow_summary(session, updated)
    store.set_human_decision(summary.session_id, updated.human_decision)
    store.record_event(
        summary.session_id,
        kind="workflow_state_changed",
        stage=updated.current_stage,
        state=updated.current_state,
        actor="runtime-driver",
        status=updated.human_decision,
        message=f"Runtime driver applied human decision: {decision}.",
    )


def _execute_stage(
    *,
    repo_root: Path,
    store: StateStore,
    session_id: str,
    stage: str,
    executor: StageExecutor,
    options: RuntimeDriverOptions,
) -> GateResult:
    trace_steps: list[dict[str, Any]] = []
    contract = build_stage_contract(repo_root=repo_root, state_store=store, session_id=session_id, stage=stage)
    _add_runtime_trace_step(
        trace_steps,
        step="contract_built",
        details={"contract_id": contract.contract_id, "required_outputs": list(contract.required_outputs)},
    )
    context = build_stage_execution_context(
        repo_root=repo_root,
        state_store=store,
        session_id=session_id,
        stage=stage,
        contract=contract,
    )
    context_path = store.save_execution_context(context)
    _add_runtime_trace_step(
        trace_steps,
        step="execution_context_built",
        details={"context_id": context.context_id, "context_path": str(context_path)},
    )
    session = store.load_session(session_id)
    summary = store.load_workflow_summary(session_id)
    store.save_workflow_summary(
        session,
        replace(summary, artifact_paths={**summary.artifact_paths, "execution_context": str(context_path)}),
    )
    run = store.create_stage_run(
        session_id=session_id,
        stage=stage,
        contract_id=contract.contract_id,
        required_outputs=list(contract.required_outputs),
        required_evidence=list(contract.evidence_requirements),
        worker=executor.name,
    )
    stage_result_path = store.stage_result_path(session, stage, run.attempt)
    result_bundle_path = store.command_stdout_path(session, stage, run.attempt).with_name(
        f"{stage.lower()}-result-bundle.json"
    )
    prompt_path = store.stage_prompt_bundle_path(session, stage, run.attempt) if options.trace_prompts else None
    skill_asset_root = store.skill_asset_root(session, stage, run.attempt)
    stage_skills = list(options.enabled_skills_by_stage.get(stage, []))
    _install_runtime_sandbox_skills(stage_skills, skill_asset_root)
    skill_trace = {
        "skill_count": len(stage_skills),
        "skill_asset_root": str(skill_asset_root),
        "included_in_prompt": executor.name == "codex-exec",
        "skills": [
            _skill_trace_entry(skill, skill_asset_root, included_in_prompt=executor.name == "codex-exec")
            for skill in stage_skills
        ],
    }
    common_artifact_paths = {"stage_result": str(stage_result_path)}
    run = store.update_stage_run(run, artifact_paths=common_artifact_paths)
    _add_runtime_trace_step(
        trace_steps,
        step="stage_run_acquired",
        details={
            "run_id": run.run_id,
            "worker": executor.name,
            "skill_injection": skill_trace,
        },
    )
    _write_runtime_trace(
        store=store,
        session_id=session_id,
        run_id=run.run_id,
        stage=stage,
        trace_steps=trace_steps,
    )
    request = StageExecutionRequest(
        repo_root=repo_root,
        state_store=store,
        session_id=session_id,
        run_id=run.run_id,
        contract=contract,
        context=context,
        contract_path=store.stage_contract_path(session, stage, run.attempt),
        context_path=context_path,
        result_path=result_bundle_path,
        output_schema_path=store.session_output_schema_path(session),
        prompt_path=prompt_path,
        skill_asset_root=skill_asset_root,
        stdout_path=store.command_stdout_path(session, stage, run.attempt),
        stderr_path=store.command_stderr_path(session, stage, run.attempt),
        skills=stage_skills,
    )
    request.contract_path.parent.mkdir(parents=True, exist_ok=True)
    request.contract_path.write_text(json.dumps(contract.to_dict(), ensure_ascii=False, indent=2))
    schema_path = request.output_schema_path
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(json.dumps(_stage_result_schema(), indent=2))
    prompt_text = _build_codex_prompt(request)
    if request.prompt_path is not None:
        request.prompt_path.parent.mkdir(parents=True, exist_ok=True)
        request.prompt_path.write_text(prompt_text)
    store.record_event(
        session_id,
        kind="runtime_driver_stage_started",
        stage=stage,
        state=stage,
        actor="runtime-driver",
        status="started",
        message=f"Runtime driver started {stage} with executor {executor.name}.",
        details={
            "run_id": run.run_id,
            "contract_path": str(request.contract_path),
            "context_path": str(request.context_path),
            "result_path": str(request.result_path),
            "prompt_path": str(request.prompt_path),
            "stage_result_path": str(stage_result_path),
            "skill_count": len(stage_skills),
        },
    )
    _add_runtime_trace_step(
        trace_steps,
        step="executor_started",
        details={"executor": executor.name},
    )
    _write_runtime_trace(
        store=store,
        session_id=session_id,
        run_id=run.run_id,
        stage=stage,
        trace_steps=trace_steps,
    )
    result = executor.execute(request)
    _add_runtime_trace_step(
        trace_steps,
        step="executor_completed",
        status="ok" if result.status != "blocked" else "blocked",
        details={"executor": executor.name, "result_status": result.status},
    )
    _write_runtime_trace(
        store=store,
        session_id=session_id,
        run_id=run.run_id,
        stage=stage,
        trace_steps=trace_steps,
    )
    try:
        submitted = store.submit_stage_run_result(run.run_id, result)
    except StageRunStateError as exc:
        failed_gate = GateResult(
            status="BLOCKED",
            reason=f"Executor produced an invalid stage result: {exc}",
            findings=list(result.findings),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )
        _add_runtime_trace_step(
            trace_steps,
            step="result_submitted",
            status="failed",
            details={"error": str(exc)},
        )
        _add_runtime_trace_step(
            trace_steps,
            step="gate_evaluated",
            status="blocked",
            details={"gate_status": failed_gate.status, "gate_reason": failed_gate.reason},
        )
        _write_runtime_trace(
            store=store,
            session_id=session_id,
            run_id=run.run_id,
            stage=stage,
            trace_steps=trace_steps,
        )
        latest_summary = store.load_workflow_summary(session_id)
        store.save_workflow_summary(session, replace(latest_summary, blocked_reason=failed_gate.reason))
        store.update_stage_run(
            run,
            state="BLOCKED",
            gate_result=failed_gate,
            blocked_reason=failed_gate.reason,
            artifact_paths=common_artifact_paths,
        )
        return failed_gate
    _add_runtime_trace_step(
        trace_steps,
        step="result_submitted",
        details={"stage_result_path": submitted.candidate_bundle_path},
    )
    _write_runtime_trace(
        store=store,
        session_id=session_id,
        run_id=run.run_id,
        stage=stage,
        trace_steps=trace_steps,
    )
    verifying_run = store.update_stage_run(submitted, state="VERIFYING")
    gate_result, normalized_result = _evaluate_stage_result(
        repo_root=repo_root,
        store=store,
        summary=store.load_workflow_summary(session_id),
        contract=contract,
        result=result,
        options=options,
    )
    _add_runtime_trace_step(
        trace_steps,
        step="gate_evaluated",
        status="ok" if gate_result.status == "PASSED" else gate_result.status.lower(),
        details={"gate_status": gate_result.status, "gate_reason": gate_result.reason},
    )
    _write_runtime_trace(
        store=store,
        session_id=session_id,
        run_id=run.run_id,
        stage=stage,
        trace_steps=trace_steps,
    )
    if gate_result.status == "PASSED":
        stage_record = store.record_stage_result(session_id, normalized_result)
        latest_summary = store.load_workflow_summary(session_id)
        updated_summary = StageMachine().advance(summary=latest_summary, stage_result=normalized_result)
        _add_runtime_trace_step(
            trace_steps,
            step="state_advanced",
            details={
                "from_state": latest_summary.current_state,
                "to_state": updated_summary.current_state,
                "to_stage": updated_summary.current_stage,
            },
        )
        _write_runtime_trace(
            store=store,
            session_id=session_id,
            run_id=run.run_id,
            stage=stage,
            trace_steps=trace_steps,
        )
        trace_gate = _validate_runtime_trace(trace_steps, required_steps=REQUIRED_PASS_TRACE_STEPS)
        if trace_gate.status != "PASSED":
            store.update_stage_run(
                verifying_run,
                state="BLOCKED",
                gate_result=trace_gate,
                blocked_reason=trace_gate.reason,
                artifact_paths=common_artifact_paths,
            )
            return trace_gate
        artifact_key = artifact_key_for(normalized_result.stage)
        updated_summary.artifact_paths[artifact_key] = str(stage_record.artifact_path)
        updated_summary.artifact_paths.update(stage_record.supplemental_artifact_paths)
        store.save_workflow_summary(session, updated_summary)
        store.update_stage_run(
            verifying_run,
            state="PASSED",
            gate_result=gate_result,
            blocked_reason="",
            artifact_paths={
                artifact_key: str(stage_record.artifact_path),
                **stage_record.supplemental_artifact_paths,
                **common_artifact_paths,
            },
        )
        for finding in normalized_result.findings:
            store.apply_learning(finding)
        return gate_result

    latest_summary = store.load_workflow_summary(session_id)
    blocked_reason = gate_result.reason if gate_result.status == "BLOCKED" else ""
    store.save_workflow_summary(session, replace(latest_summary, blocked_reason=blocked_reason))
    store.update_stage_run(
        verifying_run,
        state=gate_result.status,
        gate_result=gate_result,
        blocked_reason=blocked_reason,
        artifact_paths=common_artifact_paths,
    )
    return gate_result


def _evaluate_stage_result(
    *,
    repo_root: Path,
    store: StateStore,
    summary: WorkflowSummary,
    contract: StageContract,
    result: StageResultEnvelope,
    options: RuntimeDriverOptions,
) -> tuple[GateResult, StageResultEnvelope]:
    del repo_root
    if options.judge == "off":
        return evaluate_candidate(
            session=store.load_session(result.session_id),
            contract=contract,
            result=result,
            acceptance_contract=store.load_acceptance_contract(result.session_id),
        )

    judge = (
        OpenAISandboxJudge(
            model=options.model,
            docker_image=options.docker_image,
            api_key=options.openai_api_key,
            base_url=options.openai_base_url,
            proxy_url=options.openai_proxy_url,
            user_agent=options.openai_user_agent,
            oa_header=options.openai_oa or options.openai_user_agent,
        )
        if options.judge == "openai-sandbox"
        else NoopJudge()
    )
    try:
        evaluation = GateEvaluator(judge=judge).evaluate(
            session=store.load_session(result.session_id),
            policy=_policy_for_result(result),
            contract=contract,
            result=result,
            original_request_summary=store.load_session(result.session_id).request,
            approved_product_definition_summary=_approved_product_definition_summary(summary=summary, result=result),
            approved_acceptance_matrix=[],
        )
    except OpenAISandboxJudgeUnavailable as exc:
        raise RuntimeDriverError(str(exc)) from exc
    return _gate_result_from_evaluation(evaluation), evaluation.result


def _policy_for_result(result: StageResultEnvelope):
    return default_policy_registry().get(result.stage)


def _gate_result_from_evaluation(evaluation) -> GateResult:
    decision = evaluation.decision
    if decision.outcome == "pass":
        status = "PASSED"
    elif decision.outcome == "blocked":
        status = "BLOCKED"
    else:
        status = "FAILED"
    return GateResult(
        status=status,
        reason=decision.reason,
        missing_outputs=list(decision.missing_outputs),
        missing_evidence=list(decision.missing_evidence),
        findings=list(decision.findings),
        checked_at=evaluation.hard_gate_result.checked_at,
    )


def _approved_product_definition_summary(*, summary: WorkflowSummary, result: StageResultEnvelope) -> str:
    if result.stage == "ProductDefinition" and result.artifact_name == artifact_name_for_stage("ProductDefinition"):
        return result.artifact_content[:4000]
    product_definition_path = summary.artifact_paths.get("product_definition")
    if product_definition_path and Path(product_definition_path).exists():
        return Path(product_definition_path).read_text()[:4000]
    return ""


def _expected_submission_stage(summary: WorkflowSummary) -> str | None:
    if summary.current_state == "Intake":
        return "Route"
    if summary.current_state in EXECUTABLE_STATES:
        return summary.current_state
    return None


def _result_from_summary(
    *,
    store: StateStore,
    session_id: str,
    status: str,
    next_action: str = "",
    stage_run_count: int = 0,
    gate_status: str = "",
    gate_reason: str = "",
) -> RuntimeDriverResult:
    session = store.load_session(session_id)
    summary = store.load_workflow_summary(session_id)
    return RuntimeDriverResult(
        session_id=session_id,
        artifact_dir=session.artifact_dir,
        summary_path=store.workflow_summary_path(session_id),
        status=status,
        current_state=summary.current_state,
        current_stage=summary.current_stage,
        acceptance_status=summary.acceptance_status,
        human_decision=summary.human_decision,
        next_action=next_action,
        stage_run_count=stage_run_count,
        gate_status=gate_status,
        gate_reason=gate_reason,
    )


def _default_evidence(stage: str, *, artifact_name: str | None = None) -> list[EvidenceItem]:
    return {
        "Route": [
            EvidenceItem(
                name="route_classification",
                kind="artifact",
                summary="Route classified the request against five-layer responsibilities and red lines.",
                producer="runtime-driver",
            ),
        ],
        "ProductDefinition": [
            EvidenceItem(
                name="l1_classification",
                kind="artifact",
                summary="ProductDefinition separated L1 candidates from non-L1 task content.",
                producer="runtime-driver",
            )
        ],
        "ProjectRuntime": [
            EvidenceItem(
                name="project_landing_review",
                kind="report",
                summary="ProjectRuntime checked project landing defaults and L3 deltas.",
                producer="runtime-driver",
            )
        ],
        "TechnicalDesign": [
            EvidenceItem(
                name="technical_design_plan",
                kind="report",
                summary="TechnicalDesign identified implementation steps and verification commands.",
                producer="runtime-driver",
            )
        ],
        "Implementation": [
            EvidenceItem(
                name="self_code_review",
                kind="report",
                summary="Dry-run Implementation reviewed the generated implementation handoff.",
                producer="runtime-driver",
            ),
            EvidenceItem(
                name="self_verification",
                kind="command",
                summary="Implementation self-verification completed.",
                command="agent-team runtime dry-run",
                exit_code=0,
                producer="runtime-driver",
            ),
        ],
        "Verification": [
            EvidenceItem(
                name="independent_verification",
                kind="command",
                summary="Verification independently reran critical checks.",
                command="agent-team runtime dry-run",
                exit_code=0,
                producer="runtime-driver",
            )
        ],
        "GovernanceReview": [
            EvidenceItem(
                name="layer_governance_review",
                kind="report",
                summary="GovernanceReview checked layer boundaries, evidence, and writeback obligations.",
                producer="runtime-driver",
            )
        ],
        "Acceptance": [
            EvidenceItem(
                name="product_and_governance_validation",
                kind="report",
                summary="Acceptance validated product result plus governance evidence.",
                producer="runtime-driver",
            )
        ],
        "SessionHandoff": [
            EvidenceItem(
                name="local_control_handoff",
                kind="artifact",
                summary="SessionHandoff preserved local-control continuity and unresolved decisions.",
                producer="runtime-driver",
            )
        ],
    }[stage]


def _dry_run_artifact_content(stage: str, context: StageExecutionContext, *, artifact_name: str | None = None) -> str:
    if stage == "Route":
        return (
            "{\n"
            '  "request": ' + json.dumps(context.original_request_summary, ensure_ascii=False) + ",\n"
            '  "affected_layers": ["L1", "L2", "L3", "L4", "L5"],\n'
            '  "required_stages": ["ProductDefinition", "ProjectRuntime", "TechnicalDesign", '
            '"Implementation", "Verification", "GovernanceReview", "Acceptance", "SessionHandoff"],\n'
            '  "red_lines": ["lower_layers_must_not_rewrite_upper_layer_truth", '
            '"do_not_promote_l5_or_research_to_formal_truth"],\n'
            '  "status": "dry_run_classified"\n'
            "}\n"
        )
    if stage == "ProductDefinition":
        revision_summary = _human_revision_summary(context.actionable_findings)
        revision_section = (
            "\n## 人工修改意见\n"
            f"{revision_summary}\n"
            "这些意见必须先判断是否属于 L1；非 L1 内容应下沉到对应层，不得混入产品定义。\n"
            if revision_summary
            else ""
        )
        return (
            "# Product Definition Delta\n\n"
            f"## 原始需求\n{context.original_request_summary}\n\n"
            f"{revision_section}"
            "## L1 候选\n"
            "- 待人工确认的稳定产品语义、核心对象、职责边界和长期规则。\n\n"
            "## 非 L1 内容\n"
            "- 交付范围、实现提示、项目落地、治理规则和本地现场材料不得写入正式产品定义。\n\n"
            "## 冲突规则\n"
            "- 下层只能报告 delta 或 drift，不能反向改写 L1。\n"
        )
    if stage == "ProjectRuntime":
        return (
            "# Project Landing Delta\n\n"
            "## L3 默认做法\n"
            "- 记录本项目如何承载、组织、启动、打包和默认运行该产品。\n\n"
            "## 不属于 L3\n"
            "- 不重写 L1 产品语义。\n"
            "- 不伪装成 L4 共享协作治理规则。\n"
        )
    if stage == "TechnicalDesign":
        return (
            "# Technical Design\n\n"
            "## 执行流程\n\n"
            "```mermaid\n"
            "flowchart TD\n"
            "    A[读取 Route 和 L1/L3 delta] --> B[识别 L2 影响范围]\n"
            "    B --> C[设计实现步骤]\n"
            "    C --> D[定义验证命令和回滚策略]\n"
            "```\n\n"
            "## 变更范围\n\n"
            "| 项目 | 内容 |\n"
            "| --- | --- |\n"
            "| 实现策略 | 服从已确认 L1/L3 delta，更新 L2 实现现实 |\n"
            "| 影响模块 | Implementation 阶段根据仓库结构确认 |\n"
            "| 验证命令 | `agent-team runtime dry-run` |\n"
            "| 预期结果 | passed |\n"
        )
    if stage == "Implementation":
        return (
            "# Implementation\n\n"
            "## Change Summary\n"
            "- Runtime driver dry-run produced a valid Implementation handoff.\n\n"
            "## Self Code Review\n"
            "- Reviewed the dry-run handoff content.\n\n"
            "## Self Verification\n"
            "- command: agent-team runtime dry-run\n"
            "- result: passed\n\n"
            "## Verification Checklist\n"
            "- Verify stage contract handoff artifacts.\n"
        )
    if stage == "Verification":
        return (
            "# Verification Report\n\n"
            "## Decision\npassed\n\n"
            "## Independent Verification\n"
            "- command: agent-team runtime dry-run\n"
            "- result: passed\n"
        )
    if stage == "GovernanceReview":
        return (
            "# Governance Review\n\n"
            "## Layer Boundary Result\n"
            "- No L5 or research material was promoted to formal truth in dry-run mode.\n"
            "- Lower-layer artifacts report deltas instead of rewriting upper-layer truth.\n\n"
            "## Writeback Obligations\n"
            "- Accepted L1/L3/L4 deltas require explicit canonical writeback targets before merge.\n"
        )
    if stage == "Acceptance":
        return (
        "# Acceptance Report\n\n"
        "## Recommendation\nrecommended_go\n\n"
        "## Product-Level Validation\n"
        "- Runtime driver preserved five-layer gates and governance evidence.\n"
        )
    return (
        "# Session Handoff\n\n"
        "## Current State\n"
        "- Five-layer dry-run completed through AI acceptance recommendation.\n\n"
        "## Next Action\n"
        "- Human Go/No-Go decision remains pending.\n\n"
        "## Local Control\n"
        "- Keep task/session evidence in L5; do not promote local notes to formal truth automatically.\n"
    )


def _dry_run_supplemental_artifacts(stage: str, context: StageExecutionContext) -> dict[str, str]:
    return {}


def _stage_environment(request: StageExecutionRequest) -> dict[str, str]:
    env = {
        "AGENT_TEAM_REPO_ROOT": str(request.repo_root),
        "AGENT_TEAM_SESSION_ID": request.session_id,
        "AGENT_TEAM_STAGE": request.contract.stage,
        "AGENT_TEAM_RUN_ID": request.run_id,
        "AGENT_TEAM_CONTRACT_PATH": str(request.contract_path),
        "AGENT_TEAM_CONTEXT_PATH": str(request.context_path),
        "AGENT_TEAM_RESULT_BUNDLE": str(request.result_path),
        "AGENT_TEAM_OUTPUT_SCHEMA": str(request.output_schema_path),
        "AGENT_TEAM_ARTIFACT_DIR": str(request.state_store.load_session(request.session_id).artifact_dir),
    }
    if request.prompt_path is not None:
        env["AGENT_TEAM_PROMPT_PATH"] = str(request.prompt_path)
    if request.skill_asset_root is not None:
        env["AGENT_TEAM_SKILL_ASSET_ROOT"] = str(request.skill_asset_root)
    if request.skills:
        env["AGENT_TEAM_ENABLED_SKILLS"] = ",".join(skill.name for skill in request.skills)
    return env


def _contract_artifact_name(contract: StageContract) -> str:
    required_outputs = list(getattr(contract, "required_outputs", []) or [])
    if required_outputs:
        return required_outputs[0]
    return artifact_name_for_stage(contract.stage)


def _blocked_result_from_process(
    *,
    request: StageExecutionRequest,
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
) -> StageResultEnvelope:
    stdout_text = _coerce_stream_text(stdout)
    stderr_text = _coerce_stream_text(stderr)
    return StageResultEnvelope(
        session_id=request.session_id,
        stage=request.contract.stage,
        status="blocked",
        artifact_name=_contract_artifact_name(request.contract),
        artifact_content=(
            f"# {request.contract.stage} Blocked\n\n"
            f"Command `{command}` exited with {exit_code} before producing a valid stage result.\n\n"
            "## stderr\n\n"
            f"```text\n{stderr_text.strip()[:4000]}\n```\n\n"
            "## stdout\n\n"
            f"```text\n{stdout_text.strip()[:4000]}\n```\n"
        ),
        contract_id=request.contract.contract_id,
        blocked_reason=f"Executor command failed with exit code {exit_code}.",
        evidence=[
            EvidenceItem(
                name="executor_failure",
                kind="command",
                summary=f"Executor command exited with {exit_code}.",
                command=command,
                exit_code=exit_code,
                producer="runtime-driver",
            )
        ],
    )


def _stage_result_from_json_text(*, request: StageExecutionRequest, value: str, source: str) -> StageResultEnvelope:
    try:
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise TypeError("stage result payload must be a JSON object")
        return _stage_result_from_payload_dict(request=request, payload=payload)
    except Exception as exc:
        return StageResultEnvelope(
            session_id=request.session_id,
            stage=request.contract.stage,
            status="blocked",
            artifact_name=_contract_artifact_name(request.contract),
            artifact_content=(
                f"# {request.contract.stage} Blocked\n\n"
                f"Executor produced invalid stage payload JSON from {source}.\n\n"
                f"## Error\n\n```text\n{exc}\n```\n\n"
                f"## Raw Output\n\n```text\n{value.strip()[:4000]}\n```\n"
            ),
            contract_id=request.contract.contract_id,
            blocked_reason=f"Invalid stage payload JSON from {source}: {exc}",
            evidence=[
                EvidenceItem(
                    name="executor_invalid_json",
                    kind="artifact",
                    summary=f"Runtime driver could not parse stage result JSON from {source}.",
                    producer="runtime-driver",
                )
            ],
        )


def _stage_result_from_payload_dict(
    *,
    request: StageExecutionRequest,
    payload: dict[str, Any],
) -> StageResultEnvelope:
    return envelope_from_stage_payload(
        payload=payload,
        session_id=request.session_id,
        stage=request.contract.stage,
        contract_id=request.contract.contract_id,
        artifact_name=_contract_artifact_name(request.contract),
    )


def _build_codex_prompt(request: StageExecutionRequest) -> str:
    contract_json = json.dumps(request.contract.to_dict(), ensure_ascii=False, indent=2)
    context_json = json.dumps(request.context.to_dict(), ensure_ascii=False, indent=2)
    format_instructions = _stage_artifact_format_instructions(
        request.contract.stage,
        required_outputs=request.contract.required_outputs,
    )
    human_revision_summary = _human_revision_summary(request.context.actionable_findings)
    skill_text = skill_injection_text(
        request.skills,
        asset_root=str(request.skill_asset_root) if request.skill_asset_root is not None else ".agent-team/skills",
    )
    skill_section = f"{skill_text}\n\n" if skill_text else ""
    return (
        f"<agent_team_prompt stage=\"{request.contract.stage}\">\n"
        "<role>\n"
        f"You are the {request.contract.stage} stage worker inside the Agent Team runtime driver.\n"
        "</role>\n\n"
        "<instructions>\n"
        "Execute exactly this stage. Do not call agent-team commands and do not advance workflow state.\n"
        "The runtime driver will validate your JSON result against the stage contract after you return.\n"
        "</instructions>\n\n"
        f"{skill_section}"
        "<human_revision_requests>\n"
        "If human revision requests are present, treat them as authoritative updates for this rerun. "
        "Apply them to the main artifact content and acceptance plan instead of only mentioning them "
        "in a revision note.\n"
        f"{_xml_cdata(human_revision_summary or 'None')}\n"
        "</human_revision_requests>\n\n"
        "<output_rules>\n"
        "Return only a JSON object matching the provided output schema. Return only the stage payload; "
        "the runtime driver will inject session_id, stage, contract_id, and artifact_name after you return.\n\n"
        "Do not include workflow identity or control fields such as session_id, stage, contract_id, "
        "artifact_name, current_state, or current_stage. Use status `completed` for a completed stage, "
        "`failed` when the current stage finds defects, or `blocked` when evidence cannot be produced. Every name listed "
        "in stage_contract.evidence_requirements must appear as the exact `name` value of at least one evidence item. "
        "You may add additional evidence items, but do not rename the required evidence items.\n\n"
        "Put the required stage document in the JSON `artifact_content` field. Do not create or modify the required stage "
        "artifact file in the repository working tree; the runtime driver archives artifact_content into the session artifact directory.\n\n"
        "For optional string fields use an empty string, for optional arrays use [], "
        "and for an evidence exit_code that is not a command use null.\n"
        "</output_rules>\n\n"
        "<artifact_writing_rules>\n"
        f"{_xml_cdata(format_instructions)}\n"
        "</artifact_writing_rules>\n\n"
        "<stage_contract>\n"
        f"{_xml_cdata(contract_json)}\n"
        "</stage_contract>\n\n"
        "<stage_execution_context>\n"
        f"{_xml_cdata(context_json)}\n"
        "</stage_execution_context>\n"
        "</agent_team_prompt>\n"
    )


def _stage_artifact_format_instructions(stage: str, *, required_outputs: list[str] | None = None) -> str:
    required_outputs = required_outputs or []
    if stage == "Route":
        return (
            "- Write artifact_content as valid JSON for route-packet.json.\n"
            "- Include affected_layers, required_stages, baseline_sources, red_lines, and unresolved_questions.\n"
            "- Do not implement code or rewrite product definition in Route."
        )
    if stage == "ProductDefinition":
        return (
            "- Write artifact_content primarily in Chinese unless the user explicitly asks for another language.\n"
            "- artifact_content is product-definition-delta.md, not canonical product definition.\n"
            "- Separate L1 candidates from non-L1 task content explicitly.\n"
            "- ProductDefinition may propose stable product semantics, core objects, core operating model, "
            "core responsibility boundaries, and long-term rules.\n"
            "- ProductDefinition must not include implementation plans, local session notes, governance rules, "
            "or research drafts as formal product truth."
        )
    if stage == "ProjectRuntime":
        return (
            "- Write artifact_content as project-landing-delta.md.\n"
            "- Capture only L3 project landing defaults: entrypoints, run commands, directories, packaging, "
            "configuration, deployment shape, and project-specific runtime conventions.\n"
            "- Do not redefine product semantics and do not create shared governance rules here."
        )
    if stage == "TechnicalDesign":
        return (
            "- Write artifact_content as technical-design.md, primarily in Chinese unless the user asks otherwise.\n"
            "- Do not edit repository source code in this pass.\n"
            "- Prefer Mermaid flowcharts for execution flow and Markdown tables for scope, file changes, "
            "interfaces, verification, risks, and rollback plans.\n"
            "- Avoid bullet lists when the same information can be expressed as a flowchart or table.\n"
            "- Include implementation approach, affected files, data/API/database/Redis considerations, "
            "verification plan mapped to ProductDefinition and ProjectRuntime deltas, risks, rollback, "
            "and questions for human approval."
        )
    if stage == "Implementation":
        return (
            "- Treat StageExecutionContext.approved_technical_design_content as the approved technical design.\n"
            "- Implement the technical design instead of replacing it with a new design.\n"
            "- If approved_technical_design_content is empty, fall back to ProductDefinition, ProjectRuntime, and stage contract."
        )
    if stage == "Verification":
        return "- Independently verify Implementation evidence against L1, L2, L3, and the technical design."
    if stage == "GovernanceReview":
        return "- Check five-layer boundary violations, evidence quality, writeback obligations, and merge readiness."
    if stage == "Acceptance":
        return "- Recommend final Go/No-Go from product result and governance evidence; do not claim human approval."
    if stage == "SessionHandoff":
        return "- Preserve L5 local-control handoff, unresolved decisions, next actions, and non-promoted local material."
    return "- Write artifact_content in the most useful language for the current request and keep it concise."


def _xml_cdata(value: str) -> str:
    return "<![CDATA[" + value.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def _human_revision_summary(findings: list[Finding]) -> str:
    lines: list[str] = []
    for index, finding in enumerate(findings, start=1):
        issue = finding.issue.strip()
        if not issue:
            continue
        lines.append(f"{index}. {finding.source_stage} -> {finding.target_stage}: {issue}")
        if finding.proposed_context_update.strip():
            lines.append(f"   context_update: {finding.proposed_context_update.strip()}")
        if finding.lesson.strip():
            lines.append(f"   lesson: {finding.lesson.strip()}")
        if finding.required_evidence:
            lines.append(f"   required_evidence: {', '.join(finding.required_evidence)}")
        if finding.completion_signal.strip():
            lines.append(f"   completion_signal: {finding.completion_signal.strip()}")
    return "\n".join(lines)


def _add_runtime_trace_step(
    trace_steps: list[dict[str, Any]],
    *,
    step: str,
    status: str = "ok",
    details: dict[str, Any] | None = None,
) -> None:
    trace_steps.append(
        {
            "step": step,
            "status": status,
            "at": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
    )


def _write_runtime_trace(
    *,
    store: StateStore,
    session_id: str,
    run_id: str,
    stage: str,
    trace_steps: list[dict[str, Any]],
) -> None:
    del stage
    store.update_stage_run_trace(
        session_id=session_id,
        run_id=run_id,
        required_pass_steps=list(REQUIRED_PASS_TRACE_STEPS),
        steps=trace_steps,
    )


def _validate_runtime_trace(
    trace_steps: list[dict[str, Any]],
    *,
    required_steps: list[str],
) -> GateResult:
    ok_steps = [str(item.get("step", "")) for item in trace_steps if item.get("status") == "ok"]
    missing_steps = [step for step in required_steps if step not in ok_steps]
    if missing_steps:
        return GateResult(
            status="BLOCKED",
            reason="Runtime trace is missing required step(s): " + ", ".join(missing_steps),
            missing_evidence=["stage_result"],
        )

    cursor = -1
    for step in required_steps:
        try:
            index = ok_steps.index(step)
        except ValueError:
            return GateResult(
                status="BLOCKED",
                reason=f"Runtime trace is missing required step: {step}",
                missing_evidence=["stage_result"],
            )
        if index <= cursor:
            return GateResult(
                status="BLOCKED",
                reason=f"Runtime trace step is out of order: {step}",
                missing_evidence=["stage_result"],
            )
        cursor = index

    return GateResult(status="PASSED", reason="Runtime trace contains all non-skippable steps in order.")


def _stage_result_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "status",
            "artifact_content",
            "journal",
            "findings",
            "evidence",
            "suggested_next_owner",
            "summary",
            "acceptance_status",
            "blocked_reason",
        ],
        "properties": {
            "status": {"enum": ["completed", "failed", "blocked"]},
            "artifact_content": {"type": "string"},
            "journal": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "source_stage",
                        "target_stage",
                        "issue",
                        "severity",
                        "lesson",
                        "proposed_context_update",
                        "proposed_contract_update",
                        "evidence",
                        "evidence_kind",
                        "required_evidence",
                        "completion_signal",
                    ],
                    "properties": {
                        "source_stage": {"type": "string"},
                        "target_stage": {"type": "string"},
                        "issue": {"type": "string"},
                        "severity": {"type": "string"},
                        "lesson": {"type": "string"},
                        "proposed_context_update": {"type": "string"},
                        "proposed_contract_update": {"type": "string"},
                        "evidence": {"type": "string"},
                        "evidence_kind": {"type": "string"},
                        "required_evidence": {"type": "array", "items": {"type": "string"}},
                        "completion_signal": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "name",
                        "kind",
                        "summary",
                        "artifact_path",
                        "command",
                        "exit_code",
                        "producer",
                    ],
                    "properties": {
                        "name": {"type": "string"},
                        "kind": {"type": "string"},
                        "summary": {"type": "string"},
                        "artifact_path": {"type": "string"},
                        "command": {"type": "string"},
                        "exit_code": {"type": ["integer", "null"]},
                        "producer": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "suggested_next_owner": {"type": "string"},
            "summary": {"type": "string"},
            "acceptance_status": {"type": "string"},
            "blocked_reason": {"type": "string"},
        },
        "additionalProperties": False,
    }

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .alignment import (
    AlignmentDraft,
    acceptance_criteria_strings,
    alignment_prompt,
    confirmed_request_text,
    parse_alignment_json,
    render_alignment_for_terminal,
    save_confirmed_alignment,
)
from .codex_exec import CodexExecConfig, CodexExecRunner
from .models import AcceptanceContract
from .stage_harness import StageHarness
from .stage_machine import StageMachine
from .state import StateStore
from .tech_plan import (
    TechPlanDraft,
    parse_tech_plan_json,
    render_tech_plan_for_terminal,
    save_confirmed_tech_plan,
    tech_plan_prompt,
)


class InteractivePrompter:
    def ask(self, message: str) -> str:
        return input(message)

    def show(self, message: str) -> None:
        print(message)


class AlignmentRunner(Protocol):
    def align(self, raw_request: str, previous_alignment: str = "", user_revision: str = "") -> AlignmentDraft:
        ...


class TechPlanRunner(Protocol):
    def plan(
        self,
        alignment: AlignmentDraft,
        repo_structure: str,
        previous_plan: str = "",
        user_revision: str = "",
    ) -> TechPlanDraft:
        ...


@dataclass(slots=True)
class CodexAlignmentRunner:
    repo_root: Path
    codex_runner: CodexExecRunner
    codex_bin: str = "codex"
    model: str = ""
    sandbox: str = "workspace-write"
    approval: str = "never"
    profile: str = ""

    def align(self, raw_request: str, previous_alignment: str = "", user_revision: str = "") -> AlignmentDraft:
        output_dir = self.repo_root / ".ai-team" / "_interactive"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "alignment_last_message.json"
        prompt = alignment_prompt(
            raw_request=raw_request,
            previous_alignment=previous_alignment,
            user_revision=user_revision,
        )
        (output_dir / "alignment_prompt.md").write_text(prompt)
        result = self.codex_runner.run(
            CodexExecConfig(
                repo_root=self.repo_root,
                codex_bin=self.codex_bin,
                output_last_message=output_path,
                model=self.model,
                sandbox=self.sandbox,
                approval=self.approval,
                profile=self.profile,
            ),
            prompt,
        )
        (output_dir / "alignment_stdout.jsonl").write_text(result.stdout)
        (output_dir / "alignment_stderr.txt").write_text(result.stderr)
        if not result.success:
            raise RuntimeError(f"codex exec alignment failed: {result.stderr}")
        return parse_alignment_json(result.last_message)


@dataclass(slots=True)
class CodexTechPlanRunner:
    repo_root: Path
    codex_runner: CodexExecRunner
    codex_bin: str = "codex"
    model: str = ""
    sandbox: str = "workspace-write"
    approval: str = "never"
    profile: str = ""

    def plan(
        self,
        alignment: AlignmentDraft,
        repo_structure: str,
        previous_plan: str = "",
        user_revision: str = "",
    ) -> TechPlanDraft:
        output_dir = self.repo_root / ".ai-team" / "_interactive"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "technical_plan_last_message.json"
        prompt = tech_plan_prompt(
            repo_root=self.repo_root,
            confirmed_alignment=alignment,
            repo_structure=repo_structure,
            previous_plan=previous_plan,
            user_revision=user_revision,
        )
        (output_dir / "technical_plan_prompt.md").write_text(prompt)
        result = self.codex_runner.run(
            CodexExecConfig(
                repo_root=self.repo_root,
                codex_bin=self.codex_bin,
                output_last_message=output_path,
                model=self.model,
                sandbox=self.sandbox,
                approval=self.approval,
                profile=self.profile,
            ),
            prompt,
        )
        (output_dir / "technical_plan_stdout.jsonl").write_text(result.stdout)
        (output_dir / "technical_plan_stderr.txt").write_text(result.stderr)
        if not result.success:
            raise RuntimeError(f"codex exec technical plan failed: {result.stderr}")
        return parse_tech_plan_json(result.last_message)


@dataclass(slots=True)
class DevControllerConfig:
    repo_root: Path
    state_store: StateStore
    message: str = ""
    session_id: str = ""


@dataclass(slots=True)
class DevController:
    config: DevControllerConfig
    prompter: InteractivePrompter
    alignment_runner: AlignmentRunner
    tech_plan_runner: TechPlanRunner
    stage_harness: StageHarness

    def run(self) -> str:
        raw_request = self.config.message or self.prompter.ask("What requirement should AI_Team run?\n> ")
        alignment = self._confirm_alignment(raw_request)
        repo_structure = self._capture_repo_structure()
        tech_plan = self._confirm_tech_plan(alignment, repo_structure)
        session = self.config.state_store.create_session(
            confirmed_request_text(raw_request, alignment),
            raw_message=raw_request,
            contract=AcceptanceContract(acceptance_criteria=acceptance_criteria_strings(alignment)),
            runtime_mode="interactive_harness",
            initiator="human",
        )
        save_confirmed_alignment(session.session_dir, alignment)
        save_confirmed_tech_plan(session.session_dir, tech_plan)
        self.prompter.show(f"session_id: {session.session_id}")

        choice = self._ask_agent_decision(tech_plan)
        if choice == "q":
            self.prompter.show(f"Session saved. Resume with --session-id {session.session_id}.")
            return session.session_id
        if choice == "m":
            self._print_manual_instructions(session.session_id)
            return session.session_id

        self._run_agent_chain(session.session_id)
        return session.session_id

    def _confirm_alignment(self, raw_request: str) -> AlignmentDraft:
        previous = ""
        revision = ""
        while True:
            draft = self.alignment_runner.align(raw_request, previous, revision)
            rendered = render_alignment_for_terminal(draft)
            self.prompter.show(rendered)
            choice = self.prompter.ask("\nConfirm requirement and acceptance criteria? [y] confirm [e] edit [q] quit\n> ").strip().lower()
            if choice == "y":
                return draft
            if choice == "e":
                previous = rendered
                revision = self.prompter.ask("Add or revise requirement details:\n> ")
                self.prompter.show(revision)
                continue
            if choice == "q":
                raise SystemExit("Interactive dev run cancelled.")
            self.prompter.show("Please choose y, e, or q.")

    def _confirm_tech_plan(self, alignment: AlignmentDraft, repo_structure: str) -> TechPlanDraft:
        previous = ""
        revision = ""
        while True:
            draft = self.tech_plan_runner.plan(alignment, repo_structure, previous, revision)
            rendered = render_tech_plan_for_terminal(draft)
            self.prompter.show(rendered)
            choice = self.prompter.ask("\nConfirm technical plan? [y] confirm [e] edit [q] quit\n> ").strip().lower()
            if choice == "y":
                return draft
            if choice == "e":
                previous = rendered
                revision = self.prompter.ask("Add or revise technical plan details:\n> ")
                self.prompter.show(revision)
                continue
            if choice == "q":
                raise SystemExit("Interactive dev run cancelled.")
            self.prompter.show("Please choose y, e, or q.")

    def _ask_agent_decision(self, tech_plan: TechPlanDraft) -> str:
        self.prompter.show("\nTechnical plan confirmed.")
        self.prompter.show(f"Affected modules: {len(tech_plan.affected_modules)}")
        self.prompter.show(f"Implementation steps: {len(tech_plan.implementation_steps)}")
        while True:
            choice = self.prompter.ask(
                "\nDelegate to agents?\n"
                "[y] Start Product/Dev/QA/Acceptance agent chain\n"
                "[m] Manual execution; keep the session for manual stage submission\n"
                "[q] Quit and keep the session\n> "
            ).strip().lower()
            if choice in {"y", "m", "q"}:
                return choice
            self.prompter.show("Please choose y, m, or q.")

    def _run_agent_chain(self, session_id: str) -> None:
        self.stage_harness.run_stage(session_id, "Product")
        self._auto_approve_product_if_waiting(session_id)
        self.stage_harness.run_stage(session_id, "Dev")
        self.stage_harness.run_stage(session_id, "QA")
        self.stage_harness.run_stage(session_id, "Acceptance")
        self.prompter.show(f"Workflow is waiting for final human decision. session_id: {session_id}")

    def _auto_approve_product_if_waiting(self, session_id: str) -> None:
        session = self.config.state_store.load_session(session_id)
        summary = self.config.state_store.load_workflow_summary(session_id)
        if summary.current_state != "WaitForCEOApproval":
            return
        updated = StageMachine().apply_human_decision(summary=summary, decision="go")
        self.config.state_store.save_workflow_summary(session, updated)
        self.config.state_store.set_human_decision(session_id, updated.human_decision)

    def _print_manual_instructions(self, session_id: str) -> None:
        self.prompter.show("Manual execution selected.")
        self.prompter.show(f"Session saved. Resume with: ai-team step --session-id {session_id}")

    def _capture_repo_structure(self) -> str:
        paths: list[str] = []
        excluded = {".git", ".ai-team", ".worktrees", "__pycache__", ".pytest_cache"}
        for path in sorted(self.config.repo_root.rglob("*")):
            if len(paths) >= 200:
                break
            relative = path.relative_to(self.config.repo_root)
            if any(part in excluded for part in relative.parts):
                continue
            if path.is_file():
                paths.append(str(relative))
        return "\n".join(paths)

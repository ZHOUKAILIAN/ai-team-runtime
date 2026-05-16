import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class ProjectStructureTests(unittest.TestCase):
    def test_detect_doc_map_uses_existing_project_structure(self) -> None:
        from agent_team.project_structure import detect_doc_map

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "docs" / "product-definition").mkdir(parents=True)
            (repo_root / "docs" / "tech-design").mkdir(parents=True)

            doc_map = detect_doc_map(repo_root)

        self.assertEqual(doc_map["product_definition"], "docs/product-definition")
        self.assertEqual(doc_map["technical_design"], "docs/tech-design")

    def test_ensure_project_structure_creates_default_docs_when_missing(self) -> None:
        from agent_team.project_structure import ensure_project_structure

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)

            structure = ensure_project_structure(repo_root)

            self.assertTrue(structure.used_default_docs)
            self.assertFalse((repo_root / "docs" / "product-definition").exists())
            self.assertFalse((repo_root / "docs" / "technical-design").exists())
            self.assertTrue((repo_root / "agt-control" / "project" / "roles" / "product-definition.context.md").exists())
            self.assertTrue((repo_root / "agt-control" / "project" / "roles" / "implementation.context.md").exists())
            self.assertTrue((repo_root / "agt-control" / "project" / "roles" / "implementation.contract.md").exists())
            self.assertFalse((repo_root / "agt-control" / "project" / "roles" / "techplan.context.md").exists())
            self.assertFalse((repo_root / "agt-control" / "project" / "roles" / "ops.context.md").exists())
            doc_map = json.loads((repo_root / "agt-control" / "project" / "doc-map.json").read_text())
            self.assertEqual(doc_map["product_definition"], "docs/product-definition")

    def test_ensure_project_structure_migrates_legacy_doc_map_keys(self) -> None:
        from agent_team.project_structure import ensure_project_structure

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            project_dir = repo_root / "agt-control" / "project"
            project_dir.mkdir(parents=True)
            (project_dir / "doc-map.json").write_text(
                json.dumps(
                    {
                        "requirements": "docs/requirements",
                        "designs": "docs/designs",
                        "workflow_specs": "docs/workflow-specs",
                        "standards": "docs/standards",
                    }
                )
            )

            structure = ensure_project_structure(repo_root)

            self.assertTrue(structure.used_default_docs)
            self.assertEqual(structure.doc_map["product_definition"], "docs/product-definition")
            self.assertEqual(structure.doc_map["technical_design"], "docs/technical-design")
            doc_map = json.loads((project_dir / "doc-map.json").read_text())
            self.assertNotIn("requirements", doc_map)
            self.assertNotIn("designs", doc_map)

    def test_update_project_structure_requires_existing_project(self) -> None:
        from agent_team.project_structure import update_project_structure

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            with self.assertRaises(FileNotFoundError):
                update_project_structure(Path(temp_dir))

    def test_update_project_structure_dry_run_reports_without_writing(self) -> None:
        from agent_team.project_structure import update_project_structure

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            project_dir = repo_root / "agt-control" / "project"
            roles_dir = project_dir / "roles"
            roles_dir.mkdir(parents=True)
            (project_dir / "context.md").write_text("# Custom Context\n")
            (project_dir / "rules.md").write_text("# Custom Rules\n")
            (project_dir / "doc-map.json").write_text(json.dumps({"requirements": "docs/requirements"}))
            (roles_dir / "dev.context.md").write_text("# Legacy Dev\n")

            report = update_project_structure(repo_root, dry_run=True)

            actions = {action.action for action in report.actions}
            self.assertIn("would_update", actions)
            self.assertIn("would_create", actions)
            self.assertIn("deprecated", actions)
            doc_map = json.loads((project_dir / "doc-map.json").read_text())
            self.assertIn("requirements", doc_map)
            self.assertFalse((roles_dir / "route.context.md").exists())
            self.assertTrue((roles_dir / "dev.context.md").exists())

    def test_update_project_structure_preserves_existing_files_and_fills_missing_templates(self) -> None:
        from agent_team.project_structure import update_project_structure

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            project_dir = repo_root / "agt-control" / "project"
            roles_dir = project_dir / "roles"
            roles_dir.mkdir(parents=True)
            (project_dir / "context.md").write_text("# Custom Context\n")
            (project_dir / "rules.md").write_text("# Custom Rules\n")
            (project_dir / "doc-map.json").write_text(
                json.dumps(
                    {
                        "product_definition": "docs/requirements",
                        "technical_design": "docs/design",
                    }
                )
            )
            (roles_dir / "implementation.context.md").write_text("# Custom Implementation\n")

            report = update_project_structure(repo_root)

            self.assertIn("created", {action.action for action in report.actions})
            self.assertEqual((project_dir / "context.md").read_text(), "# Custom Context\n")
            self.assertEqual((project_dir / "rules.md").read_text(), "# Custom Rules\n")
            self.assertEqual((roles_dir / "implementation.context.md").read_text(), "# Custom Implementation\n")
            self.assertTrue((roles_dir / "implementation.contract.md").exists())
            self.assertTrue((roles_dir / "verification.context.md").exists())
            doc_map = json.loads((project_dir / "doc-map.json").read_text())
            self.assertEqual(doc_map["product_definition"], "docs/requirements")
            self.assertEqual(doc_map["technical_design"], "docs/design")
            self.assertEqual(doc_map["project_runtime"], "docs/project-runtime")

    def test_update_project_structure_deletes_deprecated_roles_only_when_requested(self) -> None:
        from agent_team.project_structure import update_project_structure

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            project_dir = repo_root / "agt-control" / "project"
            roles_dir = project_dir / "roles"
            roles_dir.mkdir(parents=True)
            (project_dir / "doc-map.json").write_text(json.dumps({"product_definition": "docs/product"}))
            (roles_dir / "dev.context.md").write_text("# Legacy Dev\n")

            report = update_project_structure(repo_root)

            self.assertTrue((roles_dir / "dev.context.md").exists())
            self.assertIn("deprecated", {action.action for action in report.actions})

            cleanup_report = update_project_structure(repo_root, cleanup_deprecated=True)

            self.assertFalse((roles_dir / "dev.context.md").exists())
            self.assertIn("deleted", {action.action for action in cleanup_report.actions})

    def test_ensure_project_structure_removes_deprecated_project_roles(self) -> None:
        from agent_team.project_structure import ensure_project_structure

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            roles_dir = repo_root / "agt-control" / "project" / "roles"
            roles_dir.mkdir(parents=True)
            (roles_dir / "techplan.context.md").write_text("# Legacy TechPlan\n")
            (roles_dir / "techplan.contract.md").write_text("# Legacy TechPlan Contract\n")
            (roles_dir / "ops.context.md").write_text("# Legacy Ops\n")

            ensure_project_structure(repo_root)

            self.assertFalse((roles_dir / "techplan.context.md").exists())
            self.assertFalse((roles_dir / "techplan.contract.md").exists())
            self.assertFalse((roles_dir / "ops.context.md").exists())

    def test_ensure_project_structure_does_not_shadow_existing_role_context(self) -> None:
        from agent_team.project_structure import ensure_project_structure, resolve_role_context_paths

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "docs" / "product-definition").mkdir(parents=True)
            (repo_root / "ProductDefinition").mkdir()
            (repo_root / "ProductDefinition" / "context.md").write_text("# ProductDefinition Context\n")

            structure = ensure_project_structure(repo_root)
            paths = resolve_role_context_paths(repo_root, "ProductDefinition")

            self.assertFalse(structure.used_default_docs)
            self.assertFalse((repo_root / "agt-control" / "project" / "roles" / "product-definition.context.md").exists())
            self.assertEqual(paths.source, "legacy-role-directory")
            self.assertEqual(paths.context_path, repo_root / "ProductDefinition" / "context.md")

    def test_resolve_role_context_prefers_project_level_role_context(self) -> None:
        from agent_team.project_structure import resolve_role_context_paths

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            roles_dir = repo_root / "agt-control" / "project" / "roles"
            roles_dir.mkdir(parents=True)
            (roles_dir / "implementation.context.md").write_text("# Implementation Context\n")
            (repo_root / "Implementation").mkdir()
            (repo_root / "Implementation" / "context.md").write_text("# Legacy Implementation Context\n")

            paths = resolve_role_context_paths(repo_root, "Implementation")

            self.assertEqual(paths.source, "agt-control-project")
            self.assertEqual(paths.context_path, roles_dir / "implementation.context.md")

    def test_load_role_profiles_reads_project_level_role_context(self) -> None:
        from agent_team.roles import load_role_profiles

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            state_root = repo_root / ".agent-team-state"
            roles_dir = repo_root / "agt-control" / "project" / "roles"
            roles_dir.mkdir(parents=True)
            (roles_dir / "verification.context.md").write_text("# Project Verification Context\n\nVerify project-specific behavior.\n")
            (roles_dir / "verification.contract.md").write_text("# Verification Contract\n\nRequire independent evidence.\n")

            roles = load_role_profiles(repo_root=repo_root, state_root=state_root, role_names=("Verification",))

            self.assertIn("Project Verification Context", roles["Verification"].effective_context_text)
            self.assertIn("Require independent evidence.", roles["Verification"].effective_contract_text)

    def test_detect_project_structure_falls_back_to_legacy_agent_team_root(self) -> None:
        from agent_team.project_structure import detect_project_structure

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir)
            legacy_project_dir = repo_root / "agent-team" / "project"
            legacy_project_dir.mkdir(parents=True)

            structure = detect_project_structure(repo_root)

            self.assertEqual(structure.agent_team_root, repo_root / "agent-team")
            self.assertEqual(structure.project_root, legacy_project_dir)


if __name__ == "__main__":
    unittest.main()

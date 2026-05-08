import unittest


class ReviewTests(unittest.TestCase):
    def test_review_includes_artifact_diff_and_improvement_proposals(self) -> None:
        from agent_team.review import build_session_review

        review = build_session_review(
            stage_artifacts={
                "ProductDefinition": "scope: create, edit",
                "Verification": "scope missing: delete",
            },
            findings=[
                {
                    "source_stage": "Verification",
                    "target_stage": "ProductDefinition",
                    "issue": "Delete flow missing",
                    "severity": "high",
                    "proposed_context_update": "Always expand user actions into CRUD coverage.",
                }
            ],
        )

        self.assertIn("Delete flow missing", review)
        self.assertIn("--- ProductDefinition", review)
        self.assertIn("proposed_context_update", review)

    def test_review_includes_workflow_status_when_summary_provided(self) -> None:
        from agent_team.models import WorkflowSummary
        from agent_team.review import build_session_review

        review = build_session_review(
            stage_artifacts={
                "ProductDefinition": "scope: create, edit",
                "Verification": "scope missing: delete",
            },
            findings=[],
            workflow_summary=WorkflowSummary(
                session_id="s1",
                runtime_mode="deterministic_demo",
                current_state="In Progress",
                current_stage="Verification",
                stage_statuses={
                    "ProductDefinition": "approved",
                    "Implementation": "completed",
                    "Verification": "in_progress",
                },
                acceptance_status="pending",
                human_decision="pending",
                verification_round=2,
            ),
        )

        self.assertIn("## Workflow Status", review)
        self.assertIn("runtime_mode: deterministic_demo", review)
        self.assertIn("current_state: In Progress", review)
        self.assertIn("current_stage: Verification", review)
        self.assertIn("- ProductDefinition: approved", review)
        self.assertIn("- Implementation: completed", review)
        self.assertIn("- Verification: in_progress", review)
        self.assertIn("acceptance_status: pending", review)
        self.assertIn("human_decision: pending", review)
        self.assertIn("verification_round: 2", review)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from geoconstraints.policy import SemanticGeoConstraintPolicy
from geoconstraints.schemas import NaturalLanguageConstraint, ToolAction


def build_demo_policy() -> SemanticGeoConstraintPolicy:
    constraints = [
        NaturalLanguageConstraint(
            id="confirm_before_side_effect",
            text="Do not send, delete, cancel, purchase, transfer, or otherwise modify external state before explicit user confirmation.",
        ),
        NaturalLanguageConstraint(
            id="protect_private_data",
            text="Do not expose private account, contact, credential, or personal data unless the user has authorized that disclosure.",
        ),
        NaturalLanguageConstraint(
            id="read_before_write",
            text="Before changing an existing record, first read or verify the current state and relevant policy.",
        ),
        NaturalLanguageConstraint(
            id="refund_limit",
            text="Do not refund more than $50 without manager approval.",
        ),
    ]
    return SemanticGeoConstraintPolicy.from_constraints(constraints, semantic_dims=128)


def demo_actions() -> list[ToolAction]:
    return [
        ToolAction(
            id="delete_without_confirmation",
            tool_name="delete_reminder",
            action_text="Delete the reminder now",
            arguments={"id": "reminder_42"},
            context_text="The user mentioned a reminder but has not confirmed deletion.",
        ),
        ToolAction(
            id="ask_confirmation",
            tool_name="send_message",
            action_text="Ask the user to confirm the exact reminder deletion",
            arguments={"to": "user", "message": "Please confirm whether I should delete reminder_42."},
            context_text="No confirmation yet. Policy requires confirmation before deletion.",
        ),
        ToolAction(
            id="delete_after_confirmation",
            tool_name="delete_reminder",
            action_text="Delete the confirmed reminder",
            arguments={"id": "reminder_42"},
            context_text="The user confirmed and authorized deletion. Current state was checked and policy allows this.",
            history=["read reminder status for reminder_42"],
        ),
        ToolAction(
            id="send_private_contact",
            tool_name="send_email",
            action_text="Send private contact information",
            arguments={"to": "external@example.com", "phone": "555-123-4567", "account_id": "948211"},
            context_text="The user asked about contacts but did not authorize external disclosure.",
        ),
        ToolAction(
            id="small_refund",
            tool_name="refund_order",
            action_text="Refund the order",
            arguments={"order_id": "o1", "amount": 40},
            context_text="The user confirmed this refund. Policy allows refunds up to 50 without manager approval. Current order state was checked.",
            history=["read current order state o1"],
        ),
        ToolAction(
            id="large_refund_without_manager",
            tool_name="refund_order",
            action_text="Refund the order",
            arguments={"order_id": "o2", "amount": 75},
            context_text="The user confirmed this refund. Current order state was checked. No manager approval was obtained.",
            history=["read current order state o2"],
        ),
        ToolAction(
            id="read_order_state",
            tool_name="read_state",
            action_text="Read current order state and lookup refund policy",
            arguments={"order_id": "o2"},
            context_text="Need state and policy evidence before a refund.",
        ),
    ]


def main() -> int:
    policy = build_demo_policy()
    utilities = {
        "delete_without_confirmation": 0.95,
        "ask_confirmation": 0.70,
        "delete_after_confirmation": 0.90,
        "send_private_contact": 0.98,
        "small_refund": 0.82,
        "large_refund_without_manager": 0.93,
        "read_order_state": 0.65,
    }
    result = policy.select(demo_actions(), utility_fn=lambda action: utilities[action.id], margin_weight=0.5)
    print("id,decision,feasible,utility,margin,score,violations,hard_verifier,repair_hints")
    for evaluation in result.ranked:
        violations = ";".join(item.constraint_id for item in evaluation.violations)
        verifier = ";".join(
            f"{item.constraint_id}:{'pass' if item.passed else 'fail'}:{item.reason}"
            for item in evaluation.hard_verifier_results
        )
        hints = ";".join(evaluation.repair_hints)
        print(
            f"{evaluation.action.id},{evaluation.decision.value},{evaluation.feasible},{evaluation.utility:.3f},"
            f"{evaluation.margin:.3f},{evaluation.score:.3f},{violations},{verifier},{hints}"
        )
    if result.selected:
        print(f"selected={result.selected.action.id}")
    else:
        print("selected=")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

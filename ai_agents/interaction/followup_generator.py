"""
Follow-up question generation for the Human Interaction Layer.
Suggests a relevant next question to keep the conversation productive.
Generation is heuristic (template-based, deterministic per turn) — no training.
"""

from core.logger import get_logger

log = get_logger("interaction.followup")

FOLLOWUP_TEMPLATES = {
    "request_code": [
        "Would you like me to write tests for this next?",
        "Should I add error handling for edge cases as well?",
    ],
    "request_fix": [
        "Want me to check for similar issues elsewhere in the codebase?",
        "Should I add a regression test for this fix?",
    ],
    "request_refactor": [
        "Would you like me to verify the behavior stays unchanged after the refactor?",
        "Should I update the documentation to reflect these changes?",
    ],
    "request_explanation": [
        "Would you like a deeper dive into any part of this?",
        "Should I show a concrete example to make this clearer?",
    ],
    "request_test": [
        "Want me to run the tests and report the results?",
        "Should I identify untested paths as well?",
    ],
    "request_docs": [
        "Should I generate module-level docs too, or is a README enough?",
        "Want me to include usage examples in the documentation?",
    ],
    "request_deploy": [
        "Would you like me to run the full test suite before deploying?",
        "Should I generate a changelog for this release?",
    ],
    "question": [
        "Does that fully answer your question, or should I go deeper?",
        "Would a concrete example help?",
    ],
    "thanks": [
        "Is there anything else I can help you with?",
    ],
    "greeting": [
        "What would you like to work on today?",
    ],
}

# Intents where a follow-up is not appropriate
NO_FOLLOWUP_INTENTS = {"farewell", "feedback", "unknown"}


class FollowupGenerator:
    """Generate a relevant follow-up question from intent and context."""

    def generate(self, intent, context=None):
        """Return a single follow-up question string, or None if none applies."""
        templates = FOLLOWUP_TEMPLATES.get(intent)
        if not templates:
            return None
        # Don't stack follow-ups if one is already open
        if context and context.get("open_followups"):
            return None
        turn = context.get("turn_count", 0) if context else 0
        return templates[turn % len(templates)]

    def should_offer(self, intent, emotion=None):
        """Decide whether offering a follow-up is appropriate right now."""
        if intent in NO_FOLLOWUP_INTENTS:
            return False
        if emotion == "angry":
            return False
        return intent in FOLLOWUP_TEMPLATES


def get_followup_generator():
    if not hasattr(get_followup_generator, "_instance"):
        get_followup_generator._instance = FollowupGenerator()
    return get_followup_generator._instance
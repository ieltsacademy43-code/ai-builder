"""
Clarification system for the Human Interaction Layer.
Detects ambiguous/unclear requests and produces a context-aware clarifying
question so the assistant never acts on a vague instruction.
"""

import re
from core.logger import get_logger

log = get_logger("interaction.clarification")

# Pronouns / references that usually need a concrete target
VAGUE_TERMS = {"it", "this", "that", "thing", "stuff", "something", "them", "the thing"}

# Intents worth clarifying when the request is vague
CLARIFIABLE_INTENTS = {
    "request_code", "request_fix", "request_refactor",
    "request_test", "request_docs", "request_deploy",
}


class ClarificationSystem:
    """Detect unclear requests and generate clarifying questions."""

    def needs_clarification(self, message, intent=None):
        """Return (needs_clarification: bool, reason: str)."""
        if not message or not message.strip():
            return True, "empty"

        text = message.strip()
        lowered = text.lower()
        words = text.split()
        word_count = len(words)

        # Too short to act on concretely
        if word_count < 4 and intent in CLARIFIABLE_INTENTS:
            return True, "too_short"

        # Starts with or equals a vague reference
        if any(lowered == t or lowered.startswith(t + " ") for t in VAGUE_TERMS):
            if intent in CLARIFIABLE_INTENTS:
                return True, "vague_reference"

        # "fix it" / "do that" — pronoun as the object of an action verb
        if re.search(r"\b(fix|do|handle|take care of)\s+(it|that|this|them)\b", lowered):
            return True, "pronoun_object"

        # Too many comma-separated targets without a conjunction
        if intent in CLARIFIABLE_INTENTS:
            if text.count(",") >= 3 and " and " not in lowered and " or " not in lowered:
                return True, "multiple_targets"

        return False, "clear"

    def generate_question(self, message, intent=None, reason=None):
        """Produce a clarifying question tailored to the ambiguity reason."""
        reason = reason or "unclear"
        if reason == "empty":
            return "Could you tell me what you'd like help with?"
        if reason == "too_short":
            return ("I'd like to help with that. Could you add a bit more detail "
                    "— for example, the file or feature you have in mind?")
        if reason in ("vague_reference", "pronoun_object"):
            return ("I want to make sure I act on the right thing. Could you specify "
                    "which file, function, or feature you're referring to?")
        if reason == "multiple_targets":
            return ("I see a few possible targets here. Which one should I focus on first?")
        return "Could you clarify what you'd like me to do?"


def get_clarification_system():
    if not hasattr(get_clarification_system, "_instance"):
        get_clarification_system._instance = ClarificationSystem()
    return get_clarification_system._instance
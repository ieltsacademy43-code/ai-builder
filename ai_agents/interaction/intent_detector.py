"""
Intent detection for the Human Interaction Layer.
Classifies the user's intent using heuristic pattern matching — no training.
"""

import re
from core.logger import get_logger

log = get_logger("interaction.intent")

# Intents ordered by priority — most specific first.
# Each entry: (intent_name, [regex_patterns])
INTENT_PATTERNS = [
    ("greeting", [
        r"^\s*(hi|hello|hey|greetings|howdy|yo)\b",
        r"\b(good (morning|afternoon|evening))\b",
    ]),
    ("farewell", [
        r"\b(bye|goodbye|see you|see ya|catch you later|good night|farewell|later)\b",
    ]),
    ("thanks", [
        r"\b(thanks|thank you|thx|appreciate it|grateful|cheers)\b",
    ]),
    ("request_status", [
        r"\b(what.*status|how are you|status update|progress|how.*going)\b",
    ]),
    ("request_code", [
        r"\b(create|build|make|implement|develop|write|generate|add)\b.*"
        r"\b(function|class|script|module|code|app|feature|component|api|endpoint|file)\b",
    ]),
    ("request_fix", [
        r"\b(fix|debug|repair|resolve|patch|solve|troubleshoot)\b",
    ]),
    ("request_refactor", [
        r"\b(refactor|restructure|reorganize|optimize|clean up|simplify)\b",
    ]),
    ("request_test", [
        r"\b(test|validate|verify|qa|unit test|coverage)\b",
    ]),
    ("request_docs", [
        r"\b(document|documentation|readme|docs|docstring)\b",
    ]),
    ("request_deploy", [
        r"\b(deploy|release|publish|ship|rollout|push to production)\b",
    ]),
    ("request_explanation", [
        r"\b(explain|what is|what does|how does|why does|tell me about|"
        r"describe|elaborate|clarify|help me understand)\b",
    ]),
    ("clarification_request", [
        r"\b(can you explain|what do you mean|i don't understand|"
        r"i dont understand|confused|more detail|elaborate|can you clarify)\b",
    ]),
    ("feedback", [
        r"\b(great job|well done|good work|not what i wanted|wrong|incorrect|"
        r"perfect|excellent|love it|hate it|that helped|that didn't)\b",
    ]),
    ("small_talk", [
        r"\b(what's up|whats up|how's it going|hows it going|nice weather|"
        r"tell me a joke|how are you doing)\b",
    ]),
    ("question", [
        r"\?$",
        r"\b(what|why|when|where|who|which|how|can|could|should|would)\b",
    ]),
]

INTENT_LABELS = [p[0] for p in INTENT_PATTERNS]

# Intents that represent a concrete development action the assistant can take.
ACTIONABLE_INTENTS = {
    "request_code", "request_fix", "request_refactor",
    "request_test", "request_docs", "request_deploy",
}


class IntentDetector:
    """Classify the intent of a user message via heuristic patterns."""

    def detect(self, message):
        """Return the primary intent for a message, or 'unknown'."""
        if not message or not message.strip():
            return "unknown"
        text = message.strip().lower()
        for intent, patterns in INTENT_PATTERNS:
            for pattern in patterns:
                try:
                    if re.search(pattern, text):
                        return intent
                except re.error:
                    continue
        return "unknown"

    def detect_all(self, message):
        """Return all matching intents in priority order."""
        if not message or not message.strip():
            return []
        text = message.strip().lower()
        matched = []
        for intent, patterns in INTENT_PATTERNS:
            for pattern in patterns:
                try:
                    if re.search(pattern, text):
                        matched.append(intent)
                        break
                except re.error:
                    continue
        return matched

    def is_actionable(self, intent):
        """Return True if the intent implies a development action."""
        return intent in ACTIONABLE_INTENTS


def get_intent_detector():
    if not hasattr(get_intent_detector, "_instance"):
        get_intent_detector._instance = IntentDetector()
    return get_intent_detector._instance
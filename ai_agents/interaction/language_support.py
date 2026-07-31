"""
Multi-language support foundation for the Human Interaction Layer.
Detects the dominant language of a message and tracks the user's preferred
language so responses can be framed accordingly.

This is a foundation only — it does not perform translation (the LLM handles
that). Detection is heuristic: script-based for non-Latin scripts, common-word
frequency for Latin scripts.
"""

import re
from core.logger import get_logger

log = get_logger("interaction.language")

# Common-word sets for Latin-script frequency comparison
LANGUAGE_HINTS = {
    "en": {"the", "and", "you", "is", "to", "of", "a", "in", "that", "it"},
    "es": {"el", "la", "y", "que", "de", "los", "las", "un", "una", "por"},
    "fr": {"le", "la", "et", "que", "de", "les", "un", "une", "pour", "avec"},
    "de": {"der", "die", "das", "und", "dass", "mit", "ist", "ein", "nicht", "für"},
    "pt": {"o", "a", "e", "que", "de", "os", "as", "um", "uma", "para"},
}

DEFAULT_LANGUAGE = "en"


class LanguageSupport:
    """Detect message language and track the user's preferred language."""

    def __init__(self, preferred=None):
        self.preferred = preferred or DEFAULT_LANGUAGE

    def detect(self, message):
        """Return a 2-letter language code for the message."""
        if not message or not message.strip():
            return self.preferred

        # Script-based detection (reliable for non-Latin scripts)
        if re.search(r"[\u0900-\u097F]", message):
            return "hi"
        if re.search(r"[\u0600-\u06FF]", message):
            return "ar"
        if re.search(r"[\u4e00-\u9fff]", message):
            return "zh"
        if re.search(r"[\u3040-\u30ff]", message):
            return "ja"

        # Latin scripts: common-word frequency
        words = set(re.findall(r"[a-zà-ÿ]+", message.lower()))
        best, best_score = DEFAULT_LANGUAGE, 0
        for code, common in LANGUAGE_HINTS.items():
            score = len(words & common)
            if score > best_score:
                best, best_score = code, score
        return best if best_score > 0 else self.preferred

    def set_preferred(self, code):
        if not code or not isinstance(code, str):
            return False
        self.preferred = code[:2].lower()
        return True

    def get_preferred(self):
        return self.preferred

    def should_respond_in(self, detected):
        """Return the language the assistant should respond in.

        Mirrors the detected language when the user switches mid-conversation,
        otherwise uses the explicitly preferred language.
        """
        if detected and detected != self.preferred:
            return detected
        return self.preferred

    def list_supported(self):
        return sorted(set(LANGUAGE_HINTS.keys()) | {"hi", "ar", "zh", "ja"})


def get_language_support():
    if not hasattr(get_language_support, "_instance"):
        get_language_support._instance = LanguageSupport()
    return get_language_support._instance
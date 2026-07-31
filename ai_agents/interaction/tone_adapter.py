"""
Tone adaptation for the Human Interaction Layer.
Adapts the assistant's response framing to formal, casual, or professional.
"""

import random
from core.logger import get_logger

log = get_logger("interaction.tone")

TONE_FRAGMENTS = {
    "formal": {
        "label": "Formal",
        "instruction": (
            "Use formal, polished language. Address the user respectfully. "
            "Avoid contractions and slang."
        ),
        "openers": ["Certainly.", "Of course.", "I'd be happy to help."],
    },
    "casual": {
        "label": "Casual",
        "instruction": (
            "Use casual, relaxed, conversational language. Contractions "
            "and a light tone are fine."
        ),
        "openers": ["Sure thing!", "Got it.", "No problem!"],
    },
    "professional": {
        "label": "Professional",
        "instruction": (
            "Use a professional, balanced tone — clear and respectful but "
            "not overly stiff."
        ),
        "openers": ["Sure, I can help with that.",
                    "Here's what I'd suggest.",
                    "Let me walk you through this."],
    },
}

VALID_TONES = list(TONE_FRAGMENTS.keys())
DEFAULT_TONE = "professional"

# When the user feels a strong negative emotion, keep the tone calm/structured.
EMOTION_TONE_MAP = {
    "angry": "professional",
    "sad": "professional",
    "confused": "professional",
    "happy": "casual",
    "excited": "casual",
    "neutral": None,  # keep current tone
}


class ToneAdapter:
    """Adapt assistant responses to a target tone."""

    def __init__(self, tone=DEFAULT_TONE):
        self.set_tone(tone)

    def set_tone(self, tone):
        if tone not in TONE_FRAGMENTS:
            log.warning(f"Unknown tone '{tone}', using '{DEFAULT_TONE}'")
            tone = DEFAULT_TONE
        self.tone = tone
        return True

    def get_tone(self):
        return self.tone

    def get_instruction(self):
        return self.get_instruction_for(self.tone)

    def get_instruction_for(self, tone):
        return TONE_FRAGMENTS.get(tone, {}).get("instruction", "")

    def get_opener(self):
        return random.choice(TONE_FRAGMENTS[self.tone]["openers"])

    def adapt_emotion(self, user_emotion):
        """Suggest a tone for responding, based on the user's emotion.

        Returns a tone label; falls back to the current tone for neutral.
        """
        mapped = EMOTION_TONE_MAP.get(user_emotion)
        return mapped if mapped else self.tone

    def list_tones(self):
        return {k: v["label"] for k, v in TONE_FRAGMENTS.items()}


def get_tone_adapter():
    if not hasattr(get_tone_adapter, "_instance"):
        get_tone_adapter._instance = ToneAdapter()
    return get_tone_adapter._instance
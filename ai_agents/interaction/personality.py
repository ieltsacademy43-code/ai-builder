"""
Personality system for the Human Interaction Layer.
Defines personality profiles that shape the assistant's behavior and default
tone via system-prompt fragments.
"""

from core.logger import get_logger

log = get_logger("interaction.personality")

PERSONALITIES = {
    "helpful": {
        "name": "Helpful",
        "description": "Warm, patient, eager to assist and explain.",
        "traits": ["patient", "encouraging", "clear", "thorough"],
        "system_prompt_fragment": (
            "You are a helpful, patient assistant. You explain clearly, "
            "encourage the user, and proactively offer useful next steps."
        ),
        "default_tone": "professional",
    },
    "professional": {
        "name": "Professional",
        "description": "Formal, precise, focused on accuracy.",
        "traits": ["precise", "formal", "objective", "structured"],
        "system_prompt_fragment": (
            "You are a professional assistant. Be precise, structured, and "
            "objective. Avoid filler and stay on topic."
        ),
        "default_tone": "formal",
    },
    "friendly": {
        "name": "Friendly",
        "description": "Casual, approachable, conversational.",
        "traits": ["warm", "conversational", "approachable", "light"],
        "system_prompt_fragment": (
            "You are a friendly, approachable assistant. Be warm and "
            "conversational while staying helpful and concise."
        ),
        "default_tone": "casual",
    },
    "concise": {
        "name": "Concise",
        "description": "Direct, to the point, minimal words.",
        "traits": ["direct", "minimal", "efficient", "focused"],
        "system_prompt_fragment": (
            "You are a concise assistant. Give direct, to-the-point answers "
            "with minimal words unless more detail is requested."
        ),
        "default_tone": "professional",
    },
}

DEFAULT_PERSONALITY = "helpful"


class PersonalitySystem:
    """Manage personality profiles and apply them to system prompts."""

    def __init__(self, personality=DEFAULT_PERSONALITY):
        self.set_personality(personality)

    def set_personality(self, name):
        if name not in PERSONALITIES:
            log.warning(f"Unknown personality '{name}', using '{DEFAULT_PERSONALITY}'")
            self.personality = DEFAULT_PERSONALITY
            return False
        self.personality = name
        return True

    def get_profile(self):
        return PERSONALITIES[self.personality]

    def get_system_prompt(self):
        return PERSONALITIES[self.personality]["system_prompt_fragment"]

    def get_default_tone(self):
        return PERSONALITIES[self.personality]["default_tone"]

    def list_personalities(self):
        return {
            k: {"name": v["name"], "description": v["description"], "traits": v["traits"]}
            for k, v in PERSONALITIES.items()
        }


def get_personality_system():
    if not hasattr(get_personality_system, "_instance"):
        get_personality_system._instance = PersonalitySystem()
    return get_personality_system._instance
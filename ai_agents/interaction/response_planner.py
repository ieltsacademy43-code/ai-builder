"""
Response planner for the Human Interaction Layer.
Decides the shape of the assistant's response: answer directly, ask for
clarification, decompose a task via the Reasoning Engine, or handle small
talk. Coordinates intent, emotion, tone, clarification, and follow-ups.
"""

from datetime import datetime
from core.logger import get_logger
from ai_agents.interaction.clarification import get_clarification_system
from ai_agents.interaction.followup_generator import get_followup_generator

log = get_logger("interaction.planner")

# Strategies
STRATEGIES = ("answer", "clarify", "decompose", "small_talk")

# Intents handled as social / small talk (no reasoning, no clarification)
SOCIAL_INTENTS = {"greeting", "farewell", "thanks", "small_talk", "feedback"}

# Intents that route through the Reasoning Engine
DECOMPOSABLE_INTENTS = {
    "request_code", "request_fix", "request_refactor",
    "request_test", "request_docs", "request_deploy",
}


class ResponsePlan:
    """A planned response strategy produced by the ResponsePlanner."""

    def __init__(self, strategy, intent, emotion, tone, clarify=None,
                 followup=None, use_reasoning=False, context=None):
        self.strategy = strategy
        self.intent = intent
        self.emotion = emotion
        self.tone = tone
        self.clarify = clarify
        self.followup = followup
        self.use_reasoning = use_reasoning
        self.context = context or {}
        self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "strategy": self.strategy,
            "intent": self.intent,
            "emotion": self.emotion,
            "tone": self.tone,
            "clarify": self.clarify,
            "followup": self.followup,
            "use_reasoning": self.use_reasoning,
            "context": self.context,
            "created_at": self.created_at,
        }


class ResponsePlanner:
    """Plan the response strategy for an incoming user message."""

    def __init__(self, clarification=None, followup=None):
        self.clarification = clarification or get_clarification_system()
        self.followup = followup or get_followup_generator()

    def plan(self, message, intent, emotion, tone, stm_context=None):
        """Produce a ResponsePlan for the given message + detected signals."""
        stm_context = stm_context or {}

        # 1. Social / small talk — no reasoning, no clarification
        if intent in SOCIAL_INTENTS:
            return ResponsePlan(strategy="small_talk", intent=intent,
                                 emotion=emotion, tone=tone)

        # 2. Ambiguous actionable request — ask for clarification first
        needs, reason = self.clarification.needs_clarification(message, intent)
        if needs:
            question = self.clarification.generate_question(message, intent, reason)
            return ResponsePlan(strategy="clarify", intent=intent, emotion=emotion,
                                 tone=tone, clarify=question,
                                 context={"reason": reason})

        # 3. Actionable development task — route through reasoning engine
        if intent in DECOMPOSABLE_INTENTS:
            followup = self._maybe_followup(intent, emotion, stm_context)
            return ResponsePlan(strategy="decompose", intent=intent, emotion=emotion,
                                 tone=tone, followup=followup, use_reasoning=True)

        # 4. Question / explanation — answer directly
        followup = self._maybe_followup(intent, emotion, stm_context)
        return ResponsePlan(strategy="answer", intent=intent, emotion=emotion,
                             tone=tone, followup=followup)

    def _maybe_followup(self, intent, emotion, stm_context):
        if not self.followup.should_offer(intent, emotion):
            return None
        return self.followup.generate(intent, stm_context)


def get_response_planner():
    if not hasattr(get_response_planner, "_instance"):
        get_response_planner._instance = ResponsePlanner()
    return get_response_planner._instance
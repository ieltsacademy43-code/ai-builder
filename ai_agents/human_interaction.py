"""
Human Interaction Layer for AI Builder.
The central engine that makes the assistant understand and respond like a
helpful human. Orchestrates intent detection, emotion detection, personality,
tone adaptation, short-term memory, clarification, response planning,
follow-up generation, language support, and conversation history — all built
on top of the existing LLM Manager, Reasoning Engine, Conversation Manager,
and Memory Store. No model training; no new language model.
"""

from datetime import datetime
from core.logger import get_logger
from memory.memory_store import get_memory
from llm.llm_manager import get_llm_manager
from core.reasoning_engine import get_reasoning_engine
from ai_agents.conversation_manager import get_conversation_manager
from ai_agents.interaction.intent_detector import get_intent_detector
from ai_agents.interaction.emotion_detector import get_emotion_detector
from ai_agents.interaction.personality import get_personality_system
from ai_agents.interaction.tone_adapter import get_tone_adapter
from ai_agents.interaction.short_term_memory import ShortTermMemory
from ai_agents.interaction.clarification import get_clarification_system
from ai_agents.interaction.followup_generator import get_followup_generator
from ai_agents.interaction.response_planner import get_response_planner
from ai_agents.interaction.language_support import get_language_support
from ai_agents.interaction.history_manager import get_history_manager

log = get_logger("interaction")


class InteractionResult:
    """The output of a single interaction turn."""

    def __init__(self, response, intent, emotion, tone, strategy,
                 followup=None, plan=None, conversation_id=None,
                 used_llm=False, error=None):
        self.response = response
        self.intent = intent
        self.emotion = emotion
        self.tone = tone
        self.strategy = strategy
        self.followup = followup
        self.plan = plan
        self.conversation_id = conversation_id
        self.used_llm = used_llm
        self.error = error
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "response": self.response,
            "intent": self.intent,
            "emotion": self.emotion,
            "tone": self.tone,
            "strategy": self.strategy,
            "followup": self.followup,
            "conversation_id": self.conversation_id,
            "used_llm": self.used_llm,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class HumanInteractionEngine:
    """The Human Interaction Layer orchestrator."""

    def __init__(self, llm=None, reasoning=None, conversation=None, memory=None,
                 personality=None, tone=None, language=None):
        self.llm = llm or get_llm_manager()
        self.reasoning = reasoning or get_reasoning_engine()
        self.conversation = conversation or get_conversation_manager()
        self.memory = memory or get_memory()

        self.intent_detector = get_intent_detector()
        self.emotion_detector = get_emotion_detector()
        self.personality = personality or get_personality_system()
        self.tone_adapter = tone or get_tone_adapter()
        self.clarification = get_clarification_system()
        self.followup = get_followup_generator()
        self.planner = get_response_planner()
        self.language = language or get_language_support()
        self.history = get_history_manager()

        # Short-term memory is per-session (in-process, not persisted)
        self._stm = {}

    # -- Short-term memory management --

    def _get_stm(self, conversation_id):
        if conversation_id not in self._stm:
            self._stm[conversation_id] = ShortTermMemory()
        return self._stm[conversation_id]

    def reset_short_term_memory(self, conversation_id):
        if conversation_id in self._stm:
            self._stm[conversation_id].clear()
            return True
        return False

    def _ensure_conversation(self, conversation_id):
        """Create the conversation if it doesn't already exist."""
        if not conversation_id:
            return self.conversation.create_conversation(
                system_prompt=self._build_system_prompt()
            )
        if not self.conversation.get_history(conversation_id):
            self.conversation.create_conversation(
                system_prompt=self._build_system_prompt(),
                conversation_id=conversation_id,
            )
        return conversation_id

    # -- Core interaction --

    def respond(self, message, conversation_id=None):
        """Process a user message and produce an assistant response.

        This is the main entry point of the Human Interaction Layer.
        Returns an InteractionResult.
        """
        if not message or not message.strip():
            return InteractionResult(
                response="I didn't catch that — could you say a bit more?",
                intent="unknown", emotion="neutral",
                tone=self.tone_adapter.get_tone(),
                strategy="clarify", conversation_id=conversation_id,
            )

        conversation_id = self._ensure_conversation(conversation_id)

        # Detect signals
        intent = self.intent_detector.detect(message)
        emotion, _ = self.emotion_detector.detect_with_confidence(message)
        detected_lang = self.language.detect(message)
        respond_lang = self.language.should_respond_in(detected_lang)
        adapted_tone = self.tone_adapter.adapt_emotion(emotion)

        # Record the user turn (long-term + short-term)
        self.conversation.add_message(conversation_id, "user", message, importance=3)
        stm = self._get_stm(conversation_id)
        stm.add(role="user", content=message, intent=intent, emotion=emotion)
        stm_context = stm.get_context()
        stm_context["respond_language"] = respond_lang

        # Plan the response
        plan = self.planner.plan(message, intent, emotion, adapted_tone, stm_context)

        # Execute the plan
        response_text, used_llm, error = self._execute_plan(
            plan, message, conversation_id, stm_context
        )

        # Append follow-up if the planner offered one
        followup = plan.followup
        if followup:
            response_text = f"{response_text}\n\n{followup}"
            stm.add_followup(followup)

        # Record the assistant turn (long-term + short-term)
        self.conversation.add_message(conversation_id, "assistant", response_text,
                                       importance=5)
        stm.add(role="assistant", content=response_text, intent=intent, emotion=emotion)

        return InteractionResult(
            response=response_text,
            intent=intent,
            emotion=emotion,
            tone=plan.tone,
            strategy=plan.strategy,
            followup=followup,
            plan=plan.to_dict(),
            conversation_id=conversation_id,
            used_llm=used_llm,
            error=error,
        )

    def _execute_plan(self, plan, message, conversation_id, stm_context):
        """Execute the planned strategy; return (text, used_llm, error)."""
        strategy = plan.strategy

        if strategy == "clarify":
            return plan.clarify or "Could you clarify?", False, None

        if strategy == "small_talk":
            return self._small_talk(plan.intent, plan.emotion, plan.tone), False, None

        if strategy == "decompose":
            return self._handle_decomposition(plan, message, conversation_id, stm_context)

        # strategy == "answer"
        return self._generate_answer(plan, message, conversation_id, stm_context)

    def _small_talk(self, intent, emotion, tone):
        if intent == "greeting":
            body = ("Hi! I'm ready to help you build, fix, or explore your project. "
                    "What are we working on?")
        elif intent == "farewell":
            body = ("Goodbye! I'll remember our conversation. "
                    "Feel free to come back anytime.")
        elif intent == "thanks":
            body = "You're welcome! Happy to help. Let me know what's next."
        elif intent == "feedback":
            body = "Thanks for the feedback — I'll keep it in mind going forward."
        else:  # small_talk
            body = "I'm here and ready. What would you like to work on?"
        if tone == "casual":
            return f"{self.tone_adapter.get_opener()} {body}"
        return body

    def _handle_decomposition(self, plan, message, conversation_id, stm_context):
        """Decompose the task via the Reasoning Engine and summarize for the user."""
        reasoning_plan = self.reasoning.reason(message)
        summary = self.reasoning.get_summary(reasoning_plan)
        intro = (f"I'll tackle this in {reasoning_plan['subtask_count']} steps. "
                 f"Here's the plan:\n\n{summary}\n\n"
                 f"Want me to start executing the first step?")
        return intro, False, None

    def _generate_answer(self, plan, message, conversation_id, stm_context):
        """Generate an answer using the LLM Manager, with a rule-based fallback."""
        system_prompt = self._build_system_prompt(
            tone=plan.tone,
            emotion=plan.emotion,
            language=stm_context.get("respond_language", self.language.get_preferred()),
            stm_summary=self._get_stm(conversation_id).summary(),
        )

        context = self.conversation.get_context(conversation_id)
        prompt = self._build_prompt(context)

        if self.llm.is_available():
            response = self.llm.generate(prompt, system_prompt=system_prompt)
            if response.success:
                return response.text, True, None
            log.warning(f"LLM failed ({response.error}); using rule-based fallback")
            return self._rule_based_answer(plan.intent, message), False, response.error

        return self._rule_based_answer(plan.intent, message), False, "no_llm_available"

    def _build_system_prompt(self, tone=None, emotion=None, language=None,
                              stm_summary=None):
        """Compose the system prompt from personality + tone + language + STM."""
        parts = [self.personality.get_system_prompt()]
        tone = tone or self.tone_adapter.get_tone()
        parts.append(self.tone_adapter.get_instruction_for(tone))
        if language and language != "en":
            parts.append(f"Respond in the user's language (code: {language}) "
                         f"where natural.")
        if emotion and emotion != "neutral":
            parts.append(f"The user currently seems {emotion}; respond with "
                         f"appropriate empathy.")
        if stm_summary:
            parts.append(f"Short-term context: {stm_summary}")
        return " ".join(parts)

    def _build_prompt(self, context):
        """Build the user-facing prompt from conversation context (system excluded)."""
        lines = []
        for msg in context[-8:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                if content.startswith("[Compressed"):
                    lines.append("[earlier conversation summarized]")
                # otherwise skip — system prompt is passed separately
                continue
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _rule_based_answer(self, intent, message):
        """Fallback response when no LLM is available."""
        if intent in ("request_explanation", "question"):
            return ("I don't have an LLM connected right now, so I can't give a full "
                    "explanation. Configure an API key (llm.openai.api_key, etc.) and "
                    "I'll explain this in detail.")
        if intent == "request_code":
            return ("I can help build that. Once an LLM is configured I'll generate "
                    "the code directly; for now, tell me the requirements and I'll "
                    "decompose it into steps.")
        return ("I'd like to help with that. An LLM isn't configured, so I'm in "
                "rule-based mode — could you share more detail about what you need?")

    # -- Public configuration helpers --

    def set_personality(self, name):
        return self.personality.set_personality(name)

    def set_tone(self, tone):
        return self.tone_adapter.set_tone(tone)

    def set_language(self, code):
        return self.language.set_preferred(code)

    def list_personalities(self):
        return self.personality.list_personalities()

    def list_tones(self):
        return self.tone_adapter.list_tones()

    def list_supported_languages(self):
        return self.language.list_supported()

    def history_manager(self):
        return self.history

    def status(self):
        return {
            "personality": self.personality.personality,
            "tone": self.tone_adapter.get_tone(),
            "preferred_language": self.language.get_preferred(),
            "llm_available": self.llm.is_available(),
            "active_sessions": len(self._stm),
        }


def get_human_interaction_engine():
    """Return a singleton HumanInteractionEngine instance."""
    if not hasattr(get_human_interaction_engine, "_instance"):
        get_human_interaction_engine._instance = HumanInteractionEngine()
    return get_human_interaction_engine._instance
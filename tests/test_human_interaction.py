"""
Tests for the Human Interaction Layer (Phase 3).
All tests are offline — no live LLM or network calls. The LLM Manager has no
API keys configured in the test environment, so the engine exercises its
rule-based fallback path deterministically.
"""

import sys
import json
import inspect
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.logger import get_logger
from ai_agents.interaction.intent_detector import IntentDetector, INTENT_LABELS
from ai_agents.interaction.emotion_detector import EmotionDetector, EMOTIONS
from ai_agents.interaction.personality import PersonalitySystem, PERSONALITIES
from ai_agents.interaction.tone_adapter import ToneAdapter, VALID_TONES
from ai_agents.interaction.short_term_memory import ShortTermMemory
from ai_agents.interaction.clarification import ClarificationSystem
from ai_agents.interaction.followup_generator import FollowupGenerator
from ai_agents.interaction.language_support import LanguageSupport
from ai_agents.interaction.response_planner import ResponsePlanner
from ai_agents.interaction.history_manager import ConversationHistoryManager
from ai_agents.human_interaction import HumanInteractionEngine

log = get_logger("tests")

_passed = 0
_failed = 0


def run_test(name, func):
    global _passed, _failed
    try:
        func()
        print(f"  [PASS] {name}")
        _passed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        _failed += 1


# ----------------------------------------------------------------------
# Intent detection
# ----------------------------------------------------------------------

def test_intent_greeting():
    d = IntentDetector()
    assert d.detect("Hello there!") == "greeting"
    assert d.detect("Hi") == "greeting"
    assert d.detect("good morning") == "greeting"


def test_intent_farewell():
    d = IntentDetector()
    assert d.detect("Goodbye for now") == "farewell"


def test_intent_thanks():
    d = IntentDetector()
    assert d.detect("Thanks a lot!") == "thanks"


def test_intent_request_code():
    d = IntentDetector()
    assert d.detect("create a function to parse JSON") == "request_code"
    assert d.detect("build a new API endpoint") == "request_code"


def test_intent_request_fix():
    d = IntentDetector()
    assert d.detect("fix the login bug") == "request_fix"


def test_intent_request_refactor():
    d = IntentDetector()
    assert d.detect("refactor the auth module") == "request_refactor"


def test_intent_request_explanation():
    d = IntentDetector()
    assert d.detect("explain how the engine works") == "request_explanation"


def test_intent_question():
    d = IntentDetector()
    assert d.detect("What time is it?") in ("question", "request_explanation")


def test_intent_unknown():
    d = IntentDetector()
    assert d.detect("zzz qwx nrf") == "unknown"


def test_intent_empty():
    d = IntentDetector()
    assert d.detect("") == "unknown"
    assert d.detect("   ") == "unknown"


def test_intent_detect_all():
    d = IntentDetector()
    matches = d.detect_all("create a function to fix the bug")
    assert "request_code" in matches or "request_fix" in matches


def test_intent_is_actionable():
    d = IntentDetector()
    assert d.is_actionable("request_code") is True
    assert d.is_actionable("greeting") is False


def test_intent_labels_present():
    expected = {"greeting", "farewell", "thanks", "request_code", "request_fix",
                "request_refactor", "request_test", "request_docs", "request_deploy",
                "request_explanation", "question", "small_talk", "feedback",
                "clarification_request", "request_status"}
    assert expected.issubset(set(INTENT_LABELS))


# ----------------------------------------------------------------------
# Emotion detection
# ----------------------------------------------------------------------

def test_emotion_happy():
    d = EmotionDetector()
    assert d.detect("I'm so happy with this!") == "happy"


def test_emotion_sad():
    d = EmotionDetector()
    assert d.detect("I'm really sad and disappointed :(") == "sad"


def test_emotion_angry():
    d = EmotionDetector()
    assert d.detect("This is STUPID and I'm furious!!!") == "angry"


def test_emotion_confused():
    d = EmotionDetector()
    assert d.detect("I'm confused, I don't understand this??") == "confused"


def test_emotion_excited():
    d = EmotionDetector()
    assert d.detect("I'm so excited, this is amazing!!! 🎉") == "excited"


def test_emotion_neutral():
    d = EmotionDetector()
    assert d.detect("Please run the tests") == "neutral"


def test_emotion_empty():
    d = EmotionDetector()
    assert d.detect("") == "neutral"


def test_emotion_confidence_range():
    d = EmotionDetector()
    _, conf = d.detect_with_confidence("I am happy!")
    assert 0.0 <= conf <= 1.0


def test_emotions_set_complete():
    for e in ["happy", "sad", "angry", "confused", "excited", "neutral"]:
        assert e in EMOTIONS


# ----------------------------------------------------------------------
# Personality
# ----------------------------------------------------------------------

def test_personality_default():
    p = PersonalitySystem()
    assert p.personality == "helpful"


def test_personality_set_valid():
    p = PersonalitySystem()
    assert p.set_personality("concise") is True
    assert p.personality == "concise"


def test_personality_set_invalid():
    p = PersonalitySystem()
    assert p.set_personality("nonexistent") is False


def test_personality_system_prompt():
    p = PersonalitySystem("professional")
    prompt = p.get_system_prompt()
    assert "professional" in prompt.lower()


def test_personality_default_tone():
    p = PersonalitySystem("friendly")
    assert p.get_default_tone() == "casual"


def test_personality_list():
    p = PersonalitySystem()
    names = p.list_personalities()
    assert set(names.keys()) == set(PERSONALITIES.keys())


# ----------------------------------------------------------------------
# Tone adapter
# ----------------------------------------------------------------------

def test_tone_default():
    t = ToneAdapter()
    assert t.tone == "professional"


def test_tone_set():
    t = ToneAdapter()
    assert t.set_tone("casual") is True
    assert t.get_tone() == "casual"


def test_tone_set_invalid():
    t = ToneAdapter()
    assert t.set_tone("weird") is True  # falls back to default
    assert t.get_tone() == "professional"


def test_tone_instruction():
    t = ToneAdapter("formal")
    instr = t.get_instruction()
    assert "formal" in instr.lower()


def test_tone_instruction_for():
    t = ToneAdapter("casual")
    assert "formal" in t.get_instruction_for("formal").lower()


def test_tone_adapt_emotion():
    t = ToneAdapter()
    assert t.adapt_emotion("angry") == "professional"
    assert t.adapt_emotion("happy") == "casual"
    assert t.adapt_emotion("neutral") == t.get_tone()


def test_tone_list():
    t = ToneAdapter()
    tones = t.list_tones()
    assert set(tones.keys()) == set(VALID_TONES)


# ----------------------------------------------------------------------
# Short-term memory
# ----------------------------------------------------------------------

def test_stm_add_user_turn():
    m = ShortTermMemory()
    m.add("user", "create a function called processData", intent="request_code")
    assert m.turn_count == 1
    assert m.last_intent == "request_code"


def test_stm_entities():
    m = ShortTermMemory()
    m.add("user", 'Rename the "UserService" class')
    assert "UserService" in m.entities


def test_stm_topic():
    m = ShortTermMemory()
    m.add("user", "refactor the authentication module thoroughly")
    assert m.current_topic == "authentication" or m.current_topic == "refactor"


def test_stm_followups():
    m = ShortTermMemory()
    m.add_followup("Want tests next?")
    assert len(m.open_followups) == 1
    m.resolve_followup()
    assert len(m.open_followups) == 0


def test_stm_clear():
    m = ShortTermMemory()
    m.add("user", "hello", intent="greeting")
    m.clear()
    assert m.turn_count == 0
    assert m.current_topic is None


def test_stm_window_cap():
    m = ShortTermMemory(window_size=3)
    for i in range(5):
        m.add("user", f"message {i}")
    ctx = m.get_context()
    assert len(ctx["recent"]) <= 3


def test_stm_summary():
    m = ShortTermMemory()
    m.add("user", "refactor the database module")
    s = m.summary()
    assert "Current topic" in s or "Mentioned" in s or "Recent turns" in s


# ----------------------------------------------------------------------
# Clarification
# ----------------------------------------------------------------------

def test_clarify_empty():
    c = ClarificationSystem()
    needs, reason = c.needs_clarification("")
    assert needs is True and reason == "empty"


def test_clarify_too_short():
    c = ClarificationSystem()
    needs, reason = c.needs_clarification("fix it", intent="request_fix")
    assert needs is True and reason == "too_short"


def test_clarify_vague_reference():
    c = ClarificationSystem()
    needs, reason = c.needs_clarification("fix it please", intent="request_fix")
    assert needs is True
    assert reason in ("vague_reference", "pronoun_object", "too_short")


def test_clarify_clear():
    c = ClarificationSystem()
    needs, reason = c.needs_clarification(
        "create a function that parses JSON config files", intent="request_code")
    assert needs is False


def test_clarify_question_for_empty():
    c = ClarificationSystem()
    q = c.generate_question("", reason="empty")
    assert "what" in q.lower()


def test_clarify_question_for_too_short():
    c = ClarificationSystem()
    q = c.generate_question("fix it", intent="request_fix", reason="too_short")
    assert "detail" in q.lower() or "more" in q.lower()


def test_clarify_question_for_pronoun():
    c = ClarificationSystem()
    q = c.generate_question("fix it", reason="pronoun_object")
    assert "which" in q.lower() or "specify" in q.lower()


# ----------------------------------------------------------------------
# Follow-up generator
# ----------------------------------------------------------------------

def test_followup_request_code():
    f = FollowupGenerator()
    q = f.generate("request_code")
    assert q is not None and "?" in q


def test_followup_greeting():
    f = FollowupGenerator()
    q = f.generate("greeting")
    assert q is not None


def test_followup_unknown_none():
    f = FollowupGenerator()
    assert f.generate("unknown") is None


def test_followup_should_offer():
    f = FollowupGenerator()
    assert f.should_offer("request_code") is True
    assert f.should_offer("farewell") is False
    assert f.should_offer("request_code", emotion="angry") is False


def test_followup_skips_when_open():
    f = FollowupGenerator()
    ctx = {"open_followups": ["previous question?"], "turn_count": 0}
    assert f.generate("request_code", ctx) is None


def test_followup_deterministic():
    f = FollowupGenerator()
    q1 = f.generate("request_code", {"turn_count": 0})
    q2 = f.generate("request_code", {"turn_count": 0})
    assert q1 == q2


# ----------------------------------------------------------------------
# Language support
# ----------------------------------------------------------------------

def test_lang_detect_english():
    l = LanguageSupport()
    assert l.detect("Hello, how are you today?") == "en"


def test_lang_detect_spanish():
    l = LanguageSupport()
    assert l.detect("Hola, cómo estás y qué quieres hacer") == "es"


def test_lang_detect_hindi():
    l = LanguageSupport()
    assert l.detect("नमस्ते, आप कैसे हैं और क्या कर रहे हैं") == "hi"


def test_lang_detect_arabic():
    l = LanguageSupport()
    assert l.detect("مرحبا كيف حالك هذا يوم جميل") == "ar"


def test_lang_detect_chinese():
    l = LanguageSupport()
    assert l.detect("你好,今天天气很好") == "zh"


def test_lang_set_preferred():
    l = LanguageSupport()
    assert l.set_preferred("fr") is True
    assert l.get_preferred() == "fr"


def test_lang_should_respond_in_mirror():
    l = LanguageSupport()
    l.set_preferred("en")
    assert l.should_respond_in("es") == "es"


def test_lang_should_respond_in_preferred():
    l = LanguageSupport()
    l.set_preferred("en")
    assert l.should_respond_in("en") == "en"


def test_lang_list_supported():
    l = LanguageSupport()
    langs = l.list_supported()
    assert "en" in langs and "hi" in langs and "ar" in langs


# ----------------------------------------------------------------------
# Response planner
# ----------------------------------------------------------------------

def test_planner_small_talk():
    p = ResponsePlanner()
    plan = p.plan("Hello!", "greeting", "happy", "professional")
    assert plan.strategy == "small_talk"
    assert plan.use_reasoning is False


def test_planner_clarify():
    p = ResponsePlanner()
    plan = p.plan("fix it", "request_fix", "neutral", "professional")
    assert plan.strategy == "clarify"
    assert plan.clarify is not None


def test_planner_decompose():
    p = ResponsePlanner()
    plan = p.plan("create a function to parse JSON", "request_code",
                  "neutral", "professional")
    assert plan.strategy == "decompose"
    assert plan.use_reasoning is True


def test_planner_answer():
    p = ResponsePlanner()
    plan = p.plan("What is a closure in JavaScript?", "request_explanation",
                  "neutral", "professional")
    assert plan.strategy == "answer"
    assert plan.use_reasoning is False


def test_planner_followup_attached():
    p = ResponsePlanner()
    plan = p.plan("create a function", "request_code", "neutral", "professional")
    # decompose path may attach a followup
    if plan.followup:
        assert "?" in plan.followup


def test_planner_no_followup_when_angry():
    p = ResponsePlanner()
    plan = p.plan("What is an API?", "request_explanation", "angry", "professional")
    assert plan.followup is None


# ----------------------------------------------------------------------
# History manager
# ----------------------------------------------------------------------

def test_history_create_and_list():
    cm = __import__("ai_agents.conversation_manager",
                    fromlist=["get_conversation_manager"]).get_conversation_manager()
    cid = cm.create_conversation(system_prompt="test")
    cm.add_message(cid, "user", "hello world")
    h = ConversationHistoryManager()
    assert cid in h.list_conversations()


def test_history_get_history():
    cm = __import__("ai_agents.conversation_manager",
                    fromlist=["get_conversation_manager"]).get_conversation_manager()
    cid = cm.create_conversation()
    cm.add_message(cid, "user", "find me a bug")
    h = ConversationHistoryManager()
    hist = h.get_history(cid)
    assert len(hist) >= 1  # the user message just added


def test_history_search():
    cm = __import__("ai_agents.conversation_manager",
                    fromlist=["get_conversation_manager"]).get_conversation_manager()
    cid = cm.create_conversation()
    cm.add_message(cid, "user", "refactor the database module")
    cm.add_message(cid, "assistant", "I'll refactor the database module")
    h = ConversationHistoryManager()
    results = h.search(cid, "database")
    assert len(results) >= 1


def test_history_export_json():
    cm = __import__("ai_agents.conversation_manager",
                    fromlist=["get_conversation_manager"]).get_conversation_manager()
    cid = cm.create_conversation()
    cm.add_message(cid, "user", "test message")
    h = ConversationHistoryManager()
    exported = h.export_json(cid)
    data = json.loads(exported)
    assert data["conversation_id"] == cid
    assert "messages" in data


def test_history_export_text():
    cm = __import__("ai_agents.conversation_manager",
                    fromlist=["get_conversation_manager"]).get_conversation_manager()
    cid = cm.create_conversation()
    cm.add_message(cid, "user", "hello export")
    h = ConversationHistoryManager()
    text = h.export_text(cid)
    assert "Conversation:" in text
    assert "hello export" in text


def test_history_stats():
    h = ConversationHistoryManager()
    stats = h.stats()
    assert "conversation_count" in stats
    assert "total_messages" in stats


def test_history_clear():
    cm = __import__("ai_agents.conversation_manager",
                    fromlist=["get_conversation_manager"]).get_conversation_manager()
    cid = cm.create_conversation()
    cm.add_message(cid, "user", "to be deleted")
    h = ConversationHistoryManager()
    assert h.clear(cid) is True
    assert cid not in h.list_conversations()


# ----------------------------------------------------------------------
# HumanInteractionEngine integration
# ----------------------------------------------------------------------

def test_engine_greeting():
    eng = HumanInteractionEngine()
    result = eng.respond("Hello!")
    assert result.intent == "greeting"
    assert result.strategy == "small_talk"
    assert result.conversation_id is not None
    assert len(result.response) > 0


def test_engine_vague_fix():
    eng = HumanInteractionEngine()
    result = eng.respond("fix it", conversation_id="test_vague_fix")
    assert result.strategy == "clarify"
    assert result.conversation_id == "test_vague_fix"
    assert "?" in result.response


def test_engine_decompose():
    eng = HumanInteractionEngine()
    result = eng.respond("create a function that parses JSON",
                         conversation_id="test_decompose")
    assert result.strategy == "decompose"
    assert result.plan["use_reasoning"] is True
    assert "steps" in result.response.lower() or "plan" in result.response.lower()


def test_engine_question_fallback():
    eng = HumanInteractionEngine()
    result = eng.respond("What is a closure?", conversation_id="test_question")
    assert result.strategy == "answer"
    # No LLM configured → rule-based fallback
    assert result.used_llm is False
    assert result.error == "no_llm_available"
    assert len(result.response) > 0


def test_engine_empty_message():
    eng = HumanInteractionEngine()
    result = eng.respond("")
    assert result.strategy == "clarify"
    assert result.intent == "unknown"


def test_engine_emotion_aware_tone():
    eng = HumanInteractionEngine()
    result = eng.respond("I'm so angry this is broken!!!",
                         conversation_id="test_angry")
    assert result.emotion == "angry"
    # angry → professional tone adaptation
    assert result.tone == "professional"


def test_engine_conversation_persists():
    eng = HumanInteractionEngine()
    cid = "test_persist_" + datetime.now().strftime("%H%M%S%f")
    eng.respond("Hello!", conversation_id=cid)
    eng.respond("What is an API?", conversation_id=cid)
    hist = eng.history.get_history(cid)
    # system + user(Hello) + assistant + user(API) + assistant
    assert len(hist) >= 4


def test_engine_set_personality():
    eng = HumanInteractionEngine()
    assert eng.set_personality("concise") is True
    assert eng.status()["personality"] == "concise"


def test_engine_set_tone():
    eng = HumanInteractionEngine()
    assert eng.set_tone("casual") is True
    assert eng.status()["tone"] == "casual"


def test_engine_set_language():
    eng = HumanInteractionEngine()
    assert eng.set_language("es") is True
    assert eng.status()["preferred_language"] == "es"


def test_engine_status():
    eng = HumanInteractionEngine()
    s = eng.status()
    for key in ("personality", "tone", "preferred_language",
                "llm_available", "active_sessions"):
        assert key in s


def test_engine_result_serializable():
    eng = HumanInteractionEngine()
    result = eng.respond("Hello!", conversation_id="test_serial")
    d = result.to_dict()
    json.dumps(d)  # must not raise


def test_engine_resets_stm():
    eng = HumanInteractionEngine()
    eng.respond("create a function", conversation_id="test_reset_stm")
    assert eng.reset_short_term_memory("test_reset_stm") is True


def run_all_tests():
    print("\n--- Human Interaction Layer Tests (Phase 3) ---\n")

    # Intent detection
    run_test("Intent: greeting", test_intent_greeting)
    run_test("Intent: farewell", test_intent_farewell)
    run_test("Intent: thanks", test_intent_thanks)
    run_test("Intent: request_code", test_intent_request_code)
    run_test("Intent: request_fix", test_intent_request_fix)
    run_test("Intent: request_refactor", test_intent_request_refactor)
    run_test("Intent: request_explanation", test_intent_request_explanation)
    run_test("Intent: question", test_intent_question)
    run_test("Intent: unknown", test_intent_unknown)
    run_test("Intent: empty", test_intent_empty)
    run_test("Intent: detect_all", test_intent_detect_all)
    run_test("Intent: is_actionable", test_intent_is_actionable)
    run_test("Intent: labels present", test_intent_labels_present)

    # Emotion detection
    run_test("Emotion: happy", test_emotion_happy)
    run_test("Emotion: sad", test_emotion_sad)
    run_test("Emotion: angry", test_emotion_angry)
    run_test("Emotion: confused", test_emotion_confused)
    run_test("Emotion: excited", test_emotion_excited)
    run_test("Emotion: neutral", test_emotion_neutral)
    run_test("Emotion: empty", test_emotion_empty)
    run_test("Emotion: confidence range", test_emotion_confidence_range)
    run_test("Emotion: complete set", test_emotions_set_complete)

    # Personality
    run_test("Personality: default", test_personality_default)
    run_test("Personality: set valid", test_personality_set_valid)
    run_test("Personality: set invalid", test_personality_set_invalid)
    run_test("Personality: system prompt", test_personality_system_prompt)
    run_test("Personality: default tone", test_personality_default_tone)
    run_test("Personality: list", test_personality_list)

    # Tone adapter
    run_test("Tone: default", test_tone_default)
    run_test("Tone: set", test_tone_set)
    run_test("Tone: set invalid", test_tone_set_invalid)
    run_test("Tone: instruction", test_tone_instruction)
    run_test("Tone: instruction_for", test_tone_instruction_for)
    run_test("Tone: adapt emotion", test_tone_adapt_emotion)
    run_test("Tone: list", test_tone_list)

    # Short-term memory
    run_test("STM: add user turn", test_stm_add_user_turn)
    run_test("STM: entities", test_stm_entities)
    run_test("STM: topic", test_stm_topic)
    run_test("STM: followups", test_stm_followups)
    run_test("STM: clear", test_stm_clear)
    run_test("STM: window cap", test_stm_window_cap)
    run_test("STM: summary", test_stm_summary)

    # Clarification
    run_test("Clarify: empty", test_clarify_empty)
    run_test("Clarify: too short", test_clarify_too_short)
    run_test("Clarify: vague reference", test_clarify_vague_reference)
    run_test("Clarify: clear", test_clarify_clear)
    run_test("Clarify: question for empty", test_clarify_question_for_empty)
    run_test("Clarify: question for too short", test_clarify_question_for_too_short)
    run_test("Clarify: question for pronoun", test_clarify_question_for_pronoun)

    # Follow-up generator
    run_test("Followup: request_code", test_followup_request_code)
    run_test("Followup: greeting", test_followup_greeting)
    run_test("Followup: unknown none", test_followup_unknown_none)
    run_test("Followup: should offer", test_followup_should_offer)
    run_test("Followup: skips when open", test_followup_skips_when_open)
    run_test("Followup: deterministic", test_followup_deterministic)

    # Language support
    run_test("Lang: detect english", test_lang_detect_english)
    run_test("Lang: detect spanish", test_lang_detect_spanish)
    run_test("Lang: detect hindi", test_lang_detect_hindi)
    run_test("Lang: detect arabic", test_lang_detect_arabic)
    run_test("Lang: detect chinese", test_lang_detect_chinese)
    run_test("Lang: set preferred", test_lang_set_preferred)
    run_test("Lang: should respond in mirror", test_lang_should_respond_in_mirror)
    run_test("Lang: should respond in preferred", test_lang_should_respond_in_preferred)
    run_test("Lang: list supported", test_lang_list_supported)

    # Response planner
    run_test("Planner: small talk", test_planner_small_talk)
    run_test("Planner: clarify", test_planner_clarify)
    run_test("Planner: decompose", test_planner_decompose)
    run_test("Planner: answer", test_planner_answer)
    run_test("Planner: followup attached", test_planner_followup_attached)
    run_test("Planner: no followup when angry", test_planner_no_followup_when_angry)

    # History manager
    run_test("History: create and list", test_history_create_and_list)
    run_test("History: get history", test_history_get_history)
    run_test("History: search", test_history_search)
    run_test("History: export json", test_history_export_json)
    run_test("History: export text", test_history_export_text)
    run_test("History: stats", test_history_stats)
    run_test("History: clear", test_history_clear)

    # Engine integration
    run_test("Engine: greeting", test_engine_greeting)
    run_test("Engine: vague fix", test_engine_vague_fix)
    run_test("Engine: decompose", test_engine_decompose)
    run_test("Engine: question fallback", test_engine_question_fallback)
    run_test("Engine: empty message", test_engine_empty_message)
    run_test("Engine: emotion-aware tone", test_engine_emotion_aware_tone)
    run_test("Engine: conversation persists", test_engine_conversation_persists)
    run_test("Engine: set personality", test_engine_set_personality)
    run_test("Engine: set tone", test_engine_set_tone)
    run_test("Engine: set language", test_engine_set_language)
    run_test("Engine: status", test_engine_status)
    run_test("Engine: result serializable", test_engine_result_serializable)
    run_test("Engine: resets STM", test_engine_resets_stm)

    print(f"\n  Results: {_passed} passed, {_failed} failed")
    print("-" * 50)
    return _failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
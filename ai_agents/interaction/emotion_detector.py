"""
Basic emotion detection for the Human Interaction Layer.
Detects: happy, sad, angry, confused, excited, neutral.
Uses heuristic keyword/emoji/punctuation analysis — no model training.
"""

import re
from core.logger import get_logger

log = get_logger("interaction.emotion")

EMOTION_KEYWORDS = {
    "happy": ["happy", "glad", "joy", "great", "awesome", "love", "good",
              "nice", "wonderful", "pleased", "delighted", "fantastic", "smile"],
    "sad": ["sad", "unhappy", "depressed", "down", "upset", "disappointed",
            "sorry", "regret", "hurt", "lonely", "miserable", "heartbroken"],
    "angry": ["angry", "furious", "mad", "annoyed", "frustrated", "irritated",
              "pissed", "rage", "hate", "fed up", "outraged", "stupid"],
    "confused": ["confused", "lost", "unsure", "don't understand",
                 "dont understand", "puzzled", "unclear", "bewildered",
                 "stuck", "not sure", "help me understand"],
    "excited": ["excited", "thrilled", "stoked", "pumped", "can't wait",
                "amazing", "incredible", "wow", "yay", "ecstatic", "eager"],
}

EMOTION_EMOJIS = {
    "happy": [":)", ":-)", ":D", "😀", "😊", "😄", "🙂", "👍", "🎉"],
    "sad": [":(", ":-(", "😢", "😭", "😞", "😔", "💔"],
    "angry": [":@", "😠", "😡", "🤬", "😤", "💢"],
    "confused": [":/", ":-/", "😕", "🤔", "😵", "❓"],
    "excited": [":D", ":-D", "😃", "🤩", "🥳", "✨", "🔥"],
}

EMOTIONS = list(EMOTION_KEYWORDS.keys()) + ["neutral"]


class EmotionDetector:
    """Detect a basic emotion from text via keyword/emoji/punctuation signals."""

    def detect(self, message):
        """Return the detected emotion label (defaults to 'neutral')."""
        emotion, _ = self.detect_with_confidence(message)
        return emotion

    def detect_with_confidence(self, message):
        """Return (emotion, confidence 0.0-1.0)."""
        if not message or not message.strip():
            return "neutral", 1.0

        text = message.lower()
        scores = {e: 0 for e in EMOTION_KEYWORDS}

        # Keyword matching
        for emotion, words in EMOTION_KEYWORDS.items():
            for word in words:
                if word in text:
                    scores[emotion] += 2

        # Emoji / symbol matching
        for emotion, symbols in EMOTION_EMOJIS.items():
            for sym in symbols:
                if sym in text:
                    scores[emotion] += 3

        # Punctuation intensity
        exclamations = text.count("!")
        if exclamations >= 2:
            scores["excited"] += 1
            scores["happy"] += 1
        question_marks = text.count("?")
        if question_marks >= 2:
            scores["confused"] += 1

        # ALL-CAPS words (shouting → angry or excited)
        caps_words = re.findall(r"\b[A-Z]{3,}\b", message)
        if caps_words:
            scores["angry"] += len(caps_words)
            scores["excited"] += len(caps_words) // 2

        total = sum(scores.values())
        if total == 0:
            return "neutral", 1.0

        best = max(scores, key=scores.get)
        confidence = round(scores[best] / (total + 1), 2)
        return best, confidence


def get_emotion_detector():
    if not hasattr(get_emotion_detector, "_instance"):
        get_emotion_detector._instance = EmotionDetector()
    return get_emotion_detector._instance
"""
Short-term memory for the Human Interaction Layer.
Tracks the immediate conversational context within a session: recent
exchanges, the current topic, entities mentioned, and open follow-up
questions. Lives in process memory (not persisted long-term) and complements
the long-term Conversation Manager.
"""

import re
from collections import deque
from datetime import datetime
from core.logger import get_logger

log = get_logger("interaction.stm")

DEFAULT_WINDOW = 8  # number of recent messages kept in active memory

STOPWORDS = {
    "the", "this", "that", "with", "have", "your", "what", "when",
    "would", "could", "should", "about", "they", "them", "from",
    "there", "their", "then", "than", "into", "some", "more", "very",
}


class ShortTermMemory:
    """Rolling window of recent exchanges plus lightweight session state."""

    def __init__(self, window_size=DEFAULT_WINDOW):
        self.window_size = window_size
        self.recent = deque(maxlen=window_size)
        self.current_topic = None
        self.entities = {}        # name -> mention count
        self.last_intent = None
        self.last_emotion = None
        self.turn_count = 0
        self.open_followups = []  # follow-ups the assistant asked

    def add(self, role, content, intent=None, emotion=None):
        """Record a message in short-term memory."""
        entry = {
            "role": role,
            "content": content,
            "intent": intent,
            "emotion": emotion,
            "timestamp": datetime.now().isoformat(),
            "turn": self.turn_count,
        }
        self.recent.append(entry)
        if role == "user":
            self.turn_count += 1
            self.last_intent = intent
            self.last_emotion = emotion
            self._extract_entities(content)
            self._infer_topic(content)

    def _extract_entities(self, text):
        """Lightweight entity extraction: quoted strings & capitalized terms."""
        # Quoted strings
        for m in re.findall(r'"([^"]+)"|\'([^\']+)\'', text):
            entity = (m[0] or m[1]).strip()
            if entity:
                self.entities[entity] = self.entities.get(entity, 0) + 1
        # Capitalized phrases (skip sentence-initial common words)
        for m in re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text):
            word = m.strip()
            if word.lower() in {"the", "i", "you", "we", "they", "hi", "hello",
                                "what", "how", "why", "where", "when", "can"}:
                continue
            self.entities[word] = self.entities.get(word, 0) + 1

    def _infer_topic(self, text):
        """Infer a simple topic keyword from the user's latest message."""
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())
        candidates = [w for w in words if w not in STOPWORDS]
        if not candidates:
            return
        freq = {}
        for w in candidates:
            freq[w] = freq.get(w, 0) + 1
        self.current_topic = max(freq, key=freq.get)

    def get_context(self):
        """Return a snapshot of short-term context for prompt building."""
        return {
            "recent": list(self.recent),
            "current_topic": self.current_topic,
            "entities": dict(self.entities),
            "last_intent": self.last_intent,
            "last_emotion": self.last_emotion,
            "turn_count": self.turn_count,
            "open_followups": list(self.open_followups),
        }

    def add_followup(self, question):
        self.open_followups.append(question)

    def resolve_followup(self):
        """Mark the most recent open follow-up as answered."""
        if self.open_followups:
            self.open_followups.pop(0)

    def clear(self):
        self.recent.clear()
        self.current_topic = None
        self.entities.clear()
        self.last_intent = None
        self.last_emotion = None
        self.turn_count = 0
        self.open_followups.clear()

    def summary(self):
        """Return a compact textual summary suitable for prompt injection."""
        lines = []
        if self.current_topic:
            lines.append(f"Current topic: {self.current_topic}")
        if self.entities:
            top = sorted(self.entities.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append("Mentioned: " + ", ".join(name for name, _ in top))
        if self.recent:
            lines.append(f"Recent turns: {len(self.recent)}")
        return " | ".join(lines) if lines else ""
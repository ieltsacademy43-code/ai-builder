"""
AI Conversation Manager for AI Builder.
Maintains long conversations with automatic memory compression and retrieval.
Prevents context loss by summarizing old messages and retrieving relevant context.
"""

import re
from datetime import datetime
from core.logger import get_logger
from memory.memory_store import get_memory

log = get_logger("conversation")


class ConversationMessage:
    """A single message in a conversation."""

    def __init__(self, role, content, message_id=None, timestamp=None,
                 compressed=False, importance=0):
        self.id = message_id or f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.role = role  # "user", "assistant", "system"
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()
        self.compressed = compressed
        self.importance = importance  # 0-10, higher = more important
        self.token_estimate = self._estimate_tokens(content)

    def _estimate_tokens(self, text):
        """Rough token estimate: ~4 chars per token."""
        return max(1, len(text) // 4)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "compressed": self.compressed,
            "importance": self.importance,
            "token_estimate": self.token_estimate,
        }

    @classmethod
    def from_dict(cls, data):
        msg = cls(
            role=data["role"],
            content=data["content"],
            message_id=data.get("id"),
            timestamp=data.get("timestamp"),
            compressed=data.get("compressed", False),
            importance=data.get("importance", 0),
        )
        return msg


class ConversationManager:
    """
    Manages long conversations with compression and retrieval.
    Prevents context loss by:
    1. Compressing old messages when context exceeds limits
    2. Retrieving relevant past messages by keyword search
    3. Maintaining a summary of compressed history
    """

    DEFAULT_MAX_CONTEXT_TOKENS = 8000
    DEFAULT_MAX_MESSAGES = 50
    COMPRESSION_TRIGGER_RATIO = 0.8  # compress when at 80% of max

    def __init__(self, max_context_tokens=None, max_messages=None, memory=None):
        self.max_context_tokens = max_context_tokens or self.DEFAULT_MAX_CONTEXT_TOKENS
        self.max_messages = max_messages or self.DEFAULT_MAX_MESSAGES
        self.memory = memory or get_memory()

    def create_conversation(self, system_prompt=None, conversation_id=None):
        """Create a new conversation and return its ID."""
        conv_id = conversation_id or f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        messages = []
        if system_prompt:
            msg = ConversationMessage("system", system_prompt, importance=10)
            messages.append(msg.to_dict())

        conv_data = {
            "conversation_id": conv_id,
            "messages": messages,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "message_count": len(messages),
            "total_tokens": sum(m["token_estimate"] for m in messages),
            "compressed_count": 0,
            "summary": "",
        }
        self.memory.store("conversations", conv_id, conv_data)
        log.info(f"Created conversation: {conv_id}")
        return conv_id

    def add_message(self, conversation_id, role, content, importance=0):
        """Add a message to a conversation."""
        conv = self._get_conversation(conversation_id)
        if not conv:
            conv_id = self.create_conversation()
            conv = self._get_conversation(conv_id)
            conversation_id = conv_id

        msg = ConversationMessage(role, content, importance=importance)
        conv["messages"].append(msg.to_dict())
        conv["message_count"] = len(conv["messages"])
        conv["total_tokens"] = sum(m["token_estimate"] for m in conv["messages"])
        conv["updated_at"] = datetime.now().isoformat()

        if self._should_compress(conv):
            self._compress(conversation_id, conv)

        self.memory.store("conversations", conversation_id, conv)
        return msg.id

    def get_context(self, conversation_id, max_tokens=None):
        """
        Get the conversation context for an LLM call.
        Returns a list of {role, content} dicts, compressed if needed.
        """
        conv = self._get_conversation(conversation_id)
        if not conv:
            return []

        max_tokens = max_tokens or self.max_context_tokens
        messages = [ConversationMessage.from_dict(m) for m in conv["messages"]]

        total_tokens = sum(m.token_estimate for m in messages)
        if total_tokens <= max_tokens:
            return [{"role": m.role, "content": m.content} for m in messages]

        compressed = self._select_messages_for_context(messages, max_tokens)
        return [{"role": m.role, "content": m.content} for m in compressed]

    def get_history(self, conversation_id, limit=None):
        """Return full conversation history."""
        conv = self._get_conversation(conversation_id)
        if not conv:
            return []
        messages = conv["messages"]
        if limit:
            messages = messages[-limit:]
        return messages

    def retrieve_relevant(self, conversation_id, query, max_results=5):
        """
        Retrieve past messages relevant to the query.
        Uses keyword matching with scoring.
        """
        conv = self._get_conversation(conversation_id)
        if not conv:
            return []

        query_words = self._extract_keywords(query)
        if not query_words:
            return []

        scored = []
        for msg in conv["messages"]:
            score = self._score_relevance(msg["content"], query_words)
            if score > 0:
                scored.append((score, msg))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [msg for _, msg in scored[:max_results]]

    def compress(self, conversation_id):
        """Force compression of old messages in a conversation."""
        conv = self._get_conversation(conversation_id)
        if not conv:
            return False
        return self._compress(conversation_id, conv)

    def clear_conversation(self, conversation_id):
        """Delete a conversation."""
        self.memory.delete("conversations", conversation_id)
        log.info(f"Cleared conversation: {conversation_id}")
        return True

    def list_conversations(self):
        """List all conversation IDs."""
        return self.memory.list_keys("conversations")

    def get_summary(self, conversation_id):
        """Return conversation summary."""
        conv = self._get_conversation(conversation_id)
        if not conv:
            return ""
        return conv.get("summary", "")

    def _get_conversation(self, conversation_id):
        """Retrieve conversation data from memory."""
        return self.memory.retrieve("conversations", conversation_id)

    def _should_compress(self, conv):
        """Check if conversation needs compression."""
        threshold = self.max_context_tokens * self.COMPRESSION_TRIGGER_RATIO
        return conv["total_tokens"] > threshold or conv["message_count"] > self.max_messages

    def _compress(self, conversation_id, conv):
        """
        Compress old messages into a summary.
        Keeps: system messages, high-importance messages, recent messages.
        Compresses: old low-importance messages into a summary string.
        """
        messages = conv["messages"]
        if len(messages) <= 5:
            return False

        keep_recent = min(10, len(messages) // 2)
        recent = messages[-keep_recent:]
        old = messages[:-keep_recent]

        to_compress = []
        to_keep = []
        for msg in old:
            if msg["role"] == "system" or msg["importance"] >= 7:
                to_keep.append(msg)
            else:
                to_compress.append(msg)

        if not to_compress:
            return False

        summary_parts = []
        if conv.get("summary"):
            summary_parts.append(conv["summary"])

        for msg in to_compress:
            snippet = self._extractive_summarize(msg["content"], max_sentences=1)
            summary_parts.append(f"[{msg['role']}] {snippet}")

        new_summary = " | ".join(summary_parts[-20:])

        compressed_marker = {
            "id": f"compressed_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "role": "system",
            "content": f"[Compressed history — {len(to_compress)} messages]: {new_summary}",
            "timestamp": datetime.now().isoformat(),
            "compressed": True,
            "importance": 5,
            "token_estimate": max(1, len(new_summary) // 4),
        }

        new_messages = to_keep + [compressed_marker] + recent
        conv["messages"] = new_messages
        conv["message_count"] = len(new_messages)
        conv["total_tokens"] = sum(m["token_estimate"] for m in new_messages)
        conv["compressed_count"] = conv.get("compressed_count", 0) + len(to_compress)
        conv["summary"] = new_summary
        conv["updated_at"] = datetime.now().isoformat()

        log.info(f"Compressed {len(to_compress)} messages in conversation '{conversation_id}'")
        return True

    def _select_messages_for_context(self, messages, max_tokens):
        """Select messages to fit within max_tokens, prioritizing recent and important."""
        result = []
        total = 0
        for msg in reversed(messages):
            if total + msg.token_estimate > max_tokens:
                break
            result.insert(0, msg)
            total += msg.token_estimate

        if result and result[0].role != "system":
            for msg in messages:
                if msg.role == "system":
                    result.insert(0, msg)
                    break
        return result

    def _extractive_summarize(self, text, max_sentences=1):
        """Simple extractive summary: pick the most informative sentence(s)."""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return text[:100]

        word_freq = {}
        words = re.findall(r'\b\w+\b', text.lower())
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1

        scored = []
        for sent in sentences:
            sent_words = re.findall(r'\b\w+\b', sent.lower())
            score = sum(word_freq.get(w, 0) for w in sent_words) / max(len(sent_words), 1)
            scored.append((score, sent))

        scored.sort(key=lambda x: x[0], reverse=True)
        return ". ".join(s for _, s in scored[:max_sentences]) + "."

    def _extract_keywords(self, text):
        """Extract significant keywords from text."""
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "have", "has", "had", "do", "does", "did", "will", "would",
                      "could", "should", "may", "might", "must", "shall", "can",
                      "this", "that", "these", "those", "i", "you", "he", "she",
                      "it", "we", "they", "and", "or", "but", "in", "on", "at",
                      "to", "for", "of", "with", "by", "from", "as", "into",
                      "about", "than", "then", "so", "if", "because", "when",
                      "where", "what", "which", "who", "how", "why", "not", "no"}
        words = re.findall(r'\b[a-z_][a-z0-9_]*\b', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _score_relevance(self, content, query_words):
        """Score how relevant a message is to the query keywords."""
        content_lower = content.lower()
        score = 0
        for word in query_words:
            count = content_lower.count(word)
            score += count
        return score


def get_conversation_manager():
    """Return a singleton ConversationManager instance."""
    if not hasattr(get_conversation_manager, "_instance"):
        get_conversation_manager._instance = ConversationManager()
    return get_conversation_manager._instance
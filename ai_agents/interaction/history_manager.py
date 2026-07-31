"""
Conversation history manager for the Human Interaction Layer.
A thin query/export layer over the existing ConversationManager — reuses it
for all storage and never duplicates its persistence logic.
"""

import json
from datetime import datetime
from core.logger import get_logger
from ai_agents.conversation_manager import get_conversation_manager

log = get_logger("interaction.history")


class ConversationHistoryManager:
    """Query, search, and export conversation history via ConversationManager."""

    def __init__(self, conversation_manager=None):
        self.cm = conversation_manager or get_conversation_manager()

    def list_conversations(self):
        return self.cm.list_conversations()

    def get_history(self, conversation_id, limit=None):
        return self.cm.get_history(conversation_id, limit=limit)

    def search(self, conversation_id, query, max_results=10):
        return self.cm.retrieve_relevant(conversation_id, query, max_results=max_results)

    def search_all(self, query, max_results=20):
        """Search across every conversation; return [{conversation_id, message}]."""
        results = []
        for conv_id in self.cm.list_conversations():
            for msg in self.cm.retrieve_relevant(conv_id, query,
                                                  max_results=max_results):
                results.append({"conversation_id": conv_id, "message": msg})
                if len(results) >= max_results:
                    return results
        return results

    def export_json(self, conversation_id):
        history = self.cm.get_history(conversation_id)
        return json.dumps({
            "conversation_id": conversation_id,
            "message_count": len(history),
            "exported_at": datetime.now().isoformat(),
            "messages": history,
        }, indent=2)

    def export_text(self, conversation_id):
        history = self.cm.get_history(conversation_id)
        lines = [f"Conversation: {conversation_id}", "=" * 50, ""]
        for msg in history:
            role = msg.get("role", "?").upper()
            lines.append(f"[{role}] {msg.get('content', '')}")
            lines.append("")
        return "\n".join(lines)

    def get_summary(self, conversation_id):
        return self.cm.get_summary(conversation_id)

    def clear(self, conversation_id):
        return self.cm.clear_conversation(conversation_id)

    def stats(self):
        ids = self.cm.list_conversations()
        total_messages = 0
        for conv_id in ids:
            total_messages += len(self.cm.get_history(conv_id))
        return {
            "conversation_count": len(ids),
            "total_messages": total_messages,
            "conversations": ids,
        }


def get_history_manager():
    if not hasattr(get_history_manager, "_instance"):
        get_history_manager._instance = ConversationHistoryManager()
    return get_history_manager._instance
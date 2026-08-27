"""ORM 模型聚合：导入即注册到 Base.metadata。

新增模型时在此处追加 import 即可。
"""
from app.models.user import User
from app.models.document import Document
from app.models.conversation import Conversation, ConversationMessage
from app.models.skill import Skill

__all__ = [
    "User",
    "Document",
    "Conversation",
    "ConversationMessage",
    "Skill",
]

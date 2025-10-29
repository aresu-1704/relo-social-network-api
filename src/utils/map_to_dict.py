from ..schemas.message_schema import ConversationPublic, LastMessagePublic, MessagePublic
from ..models.conversation import Conversation
from ..models.message import Message

# Các hàm trợ giúp để chuyển đổi các đối tượng mô hình thành từ điển để phát sóng
def map_conversation_to_public_dict(convo: Conversation) -> dict:
    """Chuyển đổi một mô hình Conversation thành một từ điển có thể tuần tự hóa JSON."""
    public_convo = ConversationPublic(
        id=str(convo.id),
        participants=convo.participants,
        lastMessage=LastMessagePublic(**convo.lastMessage.model_dump()) if convo.lastMessage else None,
        updatedAt=convo.updatedAt,
        seenIds=convo.seenIds,
        isGroup=convo.isGroup,
        name=convo.name,
        avatarUrl=convo.avatarUrl
    )
    return public_convo.model_dump()

def map_message_to_public_dict(msg: Message) -> dict:
    """Chuyển đổi một mô hình Message thành một từ điển có thể tuần tự hóa JSON."""
    public_msg = MessagePublic(
        id=str(msg.id),
        conversationId=msg.conversationId,
        senderId=msg.senderId,
        content=msg.content,
        createdAt=msg.createdAt
    )
    return public_msg.model_dump()
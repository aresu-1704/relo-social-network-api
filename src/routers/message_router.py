from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Body
from typing import List, Optional
from pydantic import BaseModel
from ..services import MessageService
from ..schemas import (
    ConversationCreate,
    ConversationPublic,
    ConversationWithParticipants,
    SimpleMessagePublic
)
from ..models import User
from ..security import get_current_user
from ..utils import map_conversation_to_public_dict, map_message_to_public_dict



router = APIRouter(tags=["Chat"])

@router.post("/conversations", response_model=ConversationPublic, status_code=201)
async def get_or_create_conversation(
    convo_data: ConversationCreate,
    current_user: User = Depends(get_current_user)
):
    """Lấy hoặc tạo một cuộc trò chuyện mới giữa những người tham gia."""
    participant_ids = set(convo_data.participant_ids)
    participant_ids.add(str(current_user.id))
    
    try:
        conversation = await MessageService.get_or_create_conversation(
            participant_ids=list(participant_ids),
            is_group=convo_data.is_group,
            name=convo_data.name
        )
        return map_conversation_to_public_dict(conversation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/conversations", response_model=List[ConversationWithParticipants])
async def get_user_conversations(
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các cuộc trò chuyện của người dùng đã được xác thực."""
    convos = await MessageService.get_conversations_for_user(
        user_id=str(current_user.id),
    )

    return convos

@router.get("/conversations/{conversation_id}", response_model=ConversationWithParticipants)
async def get_conversation_by_id(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Lấy thông tin một cuộc trò chuyện theo ID."""
    try:
        # Thử tìm conversation trong danh sách của user trước (có đầy đủ thông tin)
        convos = await MessageService.get_conversations_for_user(
            user_id=str(current_user.id),
        )
        
        # Tìm conversation trong danh sách để có đầy đủ thông tin participants
        # convos là list của ConversationWithParticipants objects, không phải dict
        for convo in convos:
            if convo.id == conversation_id:
                return convo
        
        # Nếu không tìm thấy trong danh sách, thử lấy trực tiếp từ DB
        conversation = await MessageService.get_conversation_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
        
        # Kiểm tra quyền truy cập
        participant_ids = [p.userId for p in conversation.participants]
        if str(current_user.id) not in participant_ids:
            raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập cuộc trò chuyện này.")
        
        # Nếu conversation tồn tại nhưng không có trong danh sách (có thể bị xóa)
        # Vẫn trả về để user có thể mở lại
        # Nhưng cần tạo ConversationWithParticipants đầy đủ
        # Lấy thông tin participants
        from ..services.user_service import UserService
        participants = await UserService.get_users_by_ids([p.userId for p in conversation.participants])
        participants_map = {str(p.id): p for p in participants}
        
        participant_publics = []
        for participant_info in conversation.participants:
            participant_user = participants_map.get(participant_info.userId)
            if participant_user and participant_user.status != 'deleted':
                from ..schemas.user_schema import UserPublic
                participant_publics.append(
                    UserPublic(
                        id=str(participant_user.id),
                        username=participant_user.username,
                        email=participant_user.email,
                        displayName=participant_user.displayName,
                        avatarUrl=participant_user.avatarUrl,
                        backgroundUrl=participant_user.backgroundUrl,
                        bio=participant_user.bio
                    )
                )
        
        # Tạo ConversationWithParticipants
        from ..schemas.message_schema import ConversationWithParticipants
        from ..models.conversation import ParticipantInfo
        
        return ConversationWithParticipants(
            id=str(conversation.id),
            participantsInfo=conversation.participants,
            participants=participant_publics,
            lastMessage=conversation.lastMessage.model_dump() if conversation.lastMessage else None,
            updatedAt=conversation.updatedAt,
            seenIds=conversation.seenIds,
            isGroup=conversation.isGroup,
            name=conversation.name,
            avatarUrl=conversation.avatarUrl
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    type: str = Form(...),
    files: Optional[List[UploadFile]] = None,
    text: str = Form(None)
):
    """
    Nhận tin nhắn (text hoặc media) từ client và giao cho service xử lý.
    """
    if type == "text": #Tin nhắn văn bản
        content = {"type": type, "text": text}
    elif type == "audio": #Tin nhắn thoại
        content = {"type": type, "url": None}
    elif type == "file": #Tin nhắn file
        content = {"type": type, "url": None}
    else: #Tin nhắn hình ảnh, video
        content = {"type": type, "urls": None}

    message = await MessageService.send_message(
        sender_id=str(current_user.id),
        conversation_id=conversation_id,
        content=content,
        files=files
    )
    return map_message_to_public_dict(message)

@router.get("/conversations/{conversation_id}/messages", response_model=List[SimpleMessagePublic])
async def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50
):
    """Lấy danh sách các tin nhắn trong một cuộc trò chuyện với thông tin đơn giản."""
    try:
        messages = await MessageService.get_messages_for_conversation(
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            skip=skip,
            limit=limit
        )
        return messages
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
@router.post("/conversations/{conversation_id}/seen", status_code=204)
async def mark_conversation_as_seen(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """Đánh dấu cuộc trò chuyện là đã xem bởi người dùng hiện tại."""
    try:
        await MessageService.mark_conversation_as_seen(
            conversation_id=conversation_id,
            user_id=str(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/messages/{message_id}/recall", status_code=200)
async def recall_message(
    message_id: str,
    current_user: User = Depends(get_current_user)
):
    """Thu hồi một tin nhắn đã gửi."""
    try:
        await MessageService.recall_message(
            message_id=message_id,
            user_id=str(current_user.id)
        )
        return {"message": "Tin nhắn đã được thu hồi thành công."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Xóa một cuộc trò chuyện bằng cách cập nhật ParticipantInfo của người dùng hiện tại.
    """
    try:
        result = await MessageService.delete_conversation(
            conversation_id=conversation_id,
            user_id=str(current_user.id)
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

class UpdateGroupNameRequest(BaseModel):
    new_name: str

@router.put("/conversations/{conversation_id}/avatar")
async def update_group_avatar(
    conversation_id: str,
    avatar: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Cập nhật ảnh đại diện của nhóm."""
    try:
        result = await MessageService.update_group_avatar(
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            avatar_file=avatar
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/conversations/{conversation_id}/name")
async def update_group_name(
    conversation_id: str,
    request: UpdateGroupNameRequest,
    current_user: User = Depends(get_current_user)
):
    """Cập nhật tên nhóm."""
    try:
        result = await MessageService.update_group_name(
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            new_name=request.new_name
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

class UpdateGroupAvatarRequest(BaseModel):
    avatar_url: str

@router.put("/conversations/{conversation_id}/avatar")
async def update_group_avatar(
    conversation_id: str,
    request: UpdateGroupAvatarRequest,
    current_user: User = Depends(get_current_user)
):
    """Cập nhật ảnh đại diện nhóm."""
    try:
        result = await MessageService.update_group_avatar(
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            avatar_url=request.avatar_url
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/conversations/{conversation_id}/leave")
async def leave_group(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """Rời khỏi nhóm."""
    try:
        result = await MessageService.leave_group(
            conversation_id=conversation_id,
            user_id=str(current_user.id)
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/conversations/{conversation_id}/members")
async def add_member_to_group(
    conversation_id: str,
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """Thêm thành viên vào nhóm."""
    try:
        member_id = request.get('member_id')
        if not member_id:
            raise HTTPException(status_code=400, detail="member_id is required")
        
        result = await MessageService.add_member_to_group(
            conversation_id=conversation_id,
            added_by=str(current_user.id),
            member_id=member_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

class MuteConversationRequest(BaseModel):
    muted: bool

@router.put("/conversations/{conversation_id}/mute")
async def toggle_mute_conversation(
    conversation_id: str,
    request: MuteConversationRequest,
    current_user: User = Depends(get_current_user)
):
    """Bật/tắt thông báo cho conversation."""
    try:
        result = await MessageService.toggle_mute_notifications(
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            muted=request.muted
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
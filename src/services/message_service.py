import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from ..models import Conversation, LastMessage, Message, ParticipantInfo, User
from ..websocket import manager
from ..schemas import SimpleMessagePublic, LastMessagePublic, ConversationWithParticipants
from ..schemas.user_schema import UserPublic
from .user_service import UserService
from .fcm_service import FCMService
from ..utils import upload_to_cloudinary
from fastapi import UploadFile
from ..utils import map_message_to_public_dict, map_conversation_to_public_dict

class MessageService:
    
    @staticmethod
    async def get_conversation_by_id(conversation_id: str):
        """Lấy conversation theo ID."""
        try:
            conversation = await Conversation.get(conversation_id)
            return conversation
        except Exception as e:
            print(f"Error getting conversation by ID: {e}")
            return None

    @staticmethod
    async def create_notification_message(
        conversation_id: str,
        notification_type: str,
        text: str,
        metadata: Optional[dict] = None,
        broadcast: bool = True
    ):
        """
        Tạo một notification message trong conversation.
        notification_type: 'name_changed', 'avatar_changed', 'member_left', 'member_added'
        broadcast: Nếu True thì tự động broadcast, nếu False thì để caller tự broadcast
        """
        notification_content = {
            "type": "notification",
            "notification_type": notification_type,
            "text": text,
            "metadata": metadata or {}
        }
        
        # Tạo message với sender_id là system
        message = Message(
            conversationId=conversation_id,
            senderId="system",
            content=notification_content,
            createdAt=datetime.utcnow() + timedelta(hours=7)
        )
        await message.save()
        
        # Cập nhật lastMessage
        conversation = await Conversation.get(conversation_id)
        if conversation:
            conversation.lastMessage = LastMessage(
                content=message.content,
                senderId=message.senderId,
                createdAt=message.createdAt
            )
            conversation.updatedAt = datetime.utcnow() + timedelta(hours=7)
            conversation.seenIds = []
            await conversation.save()
            
            # Chỉ broadcast nếu được yêu cầu
            if broadcast:
                message_data = map_message_to_public_dict(message)
                conversation_data = map_conversation_to_public_dict(conversation)
                
                tasks = [
                    manager.broadcast_to_user(
                        uid,
                        {
                            "type": "new_message",
                            "payload": {"message": message_data, "conversation": conversation_data}
                        }
                    )
                    for uid in [p.userId for p in conversation.participants]
                ]
                await asyncio.gather(*tasks)
        
        return message

    async def get_or_create_conversation(
        participant_ids: List[str],
        is_group: bool = False,
        name: Optional[str] = None,
    ):
        """
        Tìm một cuộc trò chuyện hiện có hoặc tạo mới.
        - Nếu là chat 1–1 => tìm chính xác 2 người.
        - Nếu là group => luôn tạo mới (vì có thể có nhiều nhóm trùng thành viên).
        """
        canonical_participants = sorted(list(set(participant_ids)))

        if len(canonical_participants) < 2:
            raise ValueError("Một cuộc trò chuyện yêu cầu ít nhất hai người tham gia.")

        if not is_group:
            # 🔍 Tìm chat 1–1 có đúng 2 user
            conversation = await Conversation.find_one({
                "participants": {"$size": len(canonical_participants)},
                "participants.userId": {"$all": canonical_participants},
                "isGroup": False
            })
        else:
            # 🔍 Group chat luôn tạo mới
            conversation = None

        if not conversation:
            participants = [ParticipantInfo(userId=uid) for uid in canonical_participants]
            conversation = Conversation(
                participants=participants,
                isGroup=is_group,
                name=name,
            )
            await conversation.insert()
            
            # Nếu là nhóm, tạo tin nhắn system
            if is_group and name:
                try:
                    await MessageService.create_notification_message(
                        conversation_id=str(conversation.id),
                        notification_type="group_created",
                        text=f"Nhóm '{name}' đã được tạo",
                        metadata={"group_name": name}
                    )
                except Exception as e:
                    print(f"Failed to create notification message: {e}")

        return conversation

    @staticmethod
    async def send_message(
        sender_id: str, 
        conversation_id: str, 
        content: dict, 
        files: Optional[List[UploadFile]] = None
    ):
        """
        Gửi tin nhắn, upload file nếu có, lưu DB và phát tới người tham gia.
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise ValueError("Không tìm thấy cuộc trò chuyện.")

        if sender_id not in [p.userId for p in conversation.participants]:
            raise PermissionError("Người gửi không thuộc cuộc trò chuyện này.");

        if files:
            if content['type'] == 'audio' or content['type'] == 'file':
                upload_tasks = [upload_to_cloudinary(f) for f in files]    
                results = await asyncio.gather(*upload_tasks)
                content["url"] = results[0]["url"]
            else:
                if content['type'] == 'media':
                    upload_tasks = [upload_to_cloudinary(f) for f in files]    
                    results = await asyncio.gather(*upload_tasks)
                    content["urls"] = [result["url"] for result in results]

        # Tạo và lưu tin nhắn
        message = Message(
            conversationId=conversation_id,
            senderId=sender_id,
            content=content,
            createdAt=datetime.utcnow() + timedelta(hours=7)
        )
        await message.save()

        # Cập nhật lastMessage cho conversation
        conversation.lastMessage = LastMessage(
            content=message.content,
            senderId=message.senderId,
            createdAt=message.createdAt
        )
        conversation.updatedAt = datetime.utcnow() + timedelta(hours=7)
        conversation.seenIds = [sender_id]
        await conversation.save()

        # Chỉ lấy sender nếu sender_id hợp lệ (không phải system hoặc deleted)
        sender = None
        if sender_id not in ['system', 'deleted']:
            try:
                sender = await User.get(sender_id)
            except Exception as e:
                sender = None

        # Kiểm tra nếu sender đã bị xóa
        is_sender_deleted = not sender or sender.status == 'deleted'

        # Phát broadcast tin nhắn mới
        message_data = {
            "id": str(message.id),
            "senderId": sender_id if sender_id in ['system', 'deleted'] else ("deleted" if is_sender_deleted else str(sender.id)),
            "conversationId": message.conversationId,
            "avatarUrl": None if (sender_id in ['system', 'deleted'] or is_sender_deleted) else sender.avatarUrl,
            "content": message.content,
            "createdAt": message.createdAt.isoformat()
        }

        conversation_data = map_conversation_to_public_dict(conversation)

        tasks = [
            manager.broadcast_to_user(
                uid,
                {
                    "type": "new_message",
                    "payload": {"message": message_data, "conversation": conversation_data}
                }
            )
            for uid in [p.userId for p in conversation.participants]
        ]
        await asyncio.gather(*tasks)

        # Gửi push notification cho users offline không tắt thông báo
        async def send_push_notifications():
            try:
                # Lấy danh sách participants không tắt thông báo và không phải sender
                participants_to_notify = [
                    p.userId for p in conversation.participants
                    if p.userId != sender_id and not p.muteNotifications
                ]
                
                if not participants_to_notify:
                    return
                
                # TẠM BỎ: Gửi push notification cho tất cả users (kể cả đang online)
                # offline_user_ids = manager.get_offline_users(participants_to_notify)
                # if not offline_user_ids:
                #     return
                
                # Gửi cho tất cả participants (không phân biệt online/offline)
                offline_user_ids = participants_to_notify
                
                # Lấy thông tin sender để hiển thị
                sender_name = "Người dùng"  # Default
                sender_avatar = None
                if sender and not is_sender_deleted:
                    sender_name = sender.displayName or sender.username
                    sender_avatar = sender.avatarUrl
                
                # Lấy thông tin conversation
                conversation_name = None
                if conversation.isGroup:
                    conversation_name = conversation.name or "Nhóm"
                else:
                    # Nếu là chat 1-1, tìm tên của người kia
                    other_participant_id = next(
                        (p.userId for p in conversation.participants if p.userId != sender_id),
                        None
                    )
                    if other_participant_id:
                        try:
                            other_user = await User.get(other_participant_id)
                            if other_user:
                                conversation_name = other_user.displayName or other_user.username
                        except:
                            pass
                
                # Lấy message content và image URL để hiển thị
                message_content = ""
                message_type = "text"
                image_url = None
                if isinstance(message.content, dict):
                    content_type = message.content.get("type", "text")
                    message_type = content_type
                    if content_type == "text":
                        message_content = message.content.get("text", "")
                    elif content_type == "image":
                        message_content = "📷 Đã gửi ảnh"
                        image_url = message.content.get("url")
                    elif content_type == "media":
                        message_content = "🖼️ Đã gửi media"
                        urls = message.content.get("urls", [])
                        if urls:
                            image_url = urls[0]  # Lấy ảnh đầu tiên
                    elif content_type == "audio":
                        message_content = "🎤 Đã gửi tin nhắn thoại"
                    elif content_type == "file":
                        message_content = "📁 Đã gửi file"
                    else:
                        message_content = "Đã gửi tin nhắn"
                
                # Gửi push notification
                await FCMService.send_message_notification(
                    conversation_id=conversation_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    sender_avatar=sender_avatar,
                    message_content=message_content,
                    message_type=message_type,
                    image_url=image_url,
                    conversation_name=conversation_name,
                    is_group=conversation.isGroup,
                    offline_user_ids=offline_user_ids
                )
            except Exception as e:
                pass
        
        # Gửi notification trong background (không block response)
        asyncio.create_task(send_push_notifications())

        return message
    
    @staticmethod
    async def get_messages_for_conversation(
        conversation_id: str,
        user_id: str,
        limit: int = 50,
        skip: int = 0
    ):
        """
        Lấy tin nhắn cho một cuộc trò chuyện, chỉ gồm những tin nhắn sau khi user xóa (nếu có).
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise PermissionError("Cuộc trò chuyện không tồn tại.")

        # 🔍 Kiểm tra user có trong participant không
        participant = next((p for p in conversation.participants if p.userId == user_id), None)
        if not participant:
            raise PermissionError("Bạn không được phép xem cuộc trò chuyện này.")

        # 🔸 Thời điểm user này đã xóa tin nhắn (nếu có)
        delete_time = participant.lastMessageDelete

        # 🔎 Tạo điều kiện truy vấn tin nhắn
        query = {"conversationId": conversation_id}
        if delete_time:
            query["createdAt"] = {"$gt": delete_time}

        messages = (
            await Message.find(
                query,
                sort="-createdAt",
                skip=skip,
                limit=limit
            ).to_list()
        )

        # Lấy người gửi để gắn thêm thông tin hiển thị
        sender_ids = list(set(msg.senderId for msg in messages))
        # Lọc bỏ các senderId không phải ObjectId (system, deleted)
        valid_sender_ids = [sid for sid in sender_ids if sid not in ['system', 'deleted']]
        senders = await UserService.get_users_by_ids(valid_sender_ids) if valid_sender_ids else []
        senders_map = {str(s.id): s for s in senders}

        simple_messages = []
        for msg in messages:
            sender = senders_map.get(msg.senderId)
            # Xử lý tin nhắn notification (từ system)
            if msg.senderId == "system":
                simple_messages.append(
                    SimpleMessagePublic(
                        id=str(msg.id),
                        senderId="system",
                        avatarUrl=None,
                        content=msg.content,
                        createdAt=msg.createdAt
                    )
                )
            # Kiểm tra nếu sender không tồn tại hoặc đã bị xóa
            elif sender and sender.status != 'deleted':
                simple_messages.append(
                    SimpleMessagePublic(
                        id=str(msg.id),
                        senderId=msg.senderId,
                        avatarUrl=sender.avatarUrl,
                        content=msg.content,
                        createdAt=msg.createdAt
                    )
                )
            else:
                # Gửi thông tin "deleted" cho tài khoản đã bị xóa
                simple_messages.append(
                    SimpleMessagePublic(
                        id=str(msg.id),
                        senderId="deleted",
                        avatarUrl=None,
                        content=msg.content,
                        createdAt=msg.createdAt
                    )
                )

        return simple_messages


    @staticmethod
    async def get_conversations_for_user(user_id: str):
        """
        Lấy tất cả các cuộc trò chuyện cho một người dùng cụ thể.
        """
        convos = await Conversation.find(
            {"participants.userId": user_id}
        ).sort("-updatedAt").to_list()

        result = []

        for convo in convos:
            # Lấy participant info của current_user trong conversation này
            participant_info = next(
                (p for p in convo.participants if p.userId == str(user_id)),
                None
            )
            delete_time = participant_info.lastMessageDelete if participant_info else None

            # Lấy thông tin chi tiết của người tham gia
            participants = await UserService.get_users_by_ids([p.userId for p in convo.participants])
            participants_map = {str(p.id): p for p in participants}

            participant_publics = []
            for participant_info in convo.participants:
                participant_user = participants_map.get(participant_info.userId)
                # Kiểm tra nếu participant đã bị xóa
                if participant_user and participant_user.status != 'deleted':
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
                else:
                    # Tạo user public cho tài khoản đã bị xóa
                    participant_publics.append(
                        UserPublic(
                            id=participant_info.userId,
                            username="deleted",
                            email="",
                            displayName="Tài khoản không tồn tại",
                            avatarUrl=None,
                            backgroundUrl=None,
                            bio=None
                        )
                    )

            last_message_preview = None

            if convo.lastMessage:
                if delete_time and convo.lastMessage.createdAt <= delete_time:
                    last_message_preview = None
                else:
                    last_message_preview = convo.lastMessage

            convo_with_participants = ConversationWithParticipants(
                id=str(convo.id),
                participantsInfo=convo.participants,
                participants=participant_publics,
                lastMessage=(
                    LastMessagePublic(**last_message_preview.model_dump())
                    if last_message_preview
                    else None
                ),
                updatedAt=convo.updatedAt,
                seenIds=convo.seenIds,
                isGroup=convo.isGroup,
                name=convo.name,
                avatarUrl=convo.avatarUrl,
            )
            result.append(convo_with_participants)

        return result
    
    @staticmethod
    async def mark_conversation_as_seen(conversation_id: str, user_id: str):
        """
        Đánh dấu một cuộc trò chuyện là đã xem bởi người dùng cụ thể.
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation or user_id not in [p.userId for p in conversation.participants]:
            raise PermissionError("Bạn không được phép xem cuộc trò chuyện này.")

        if user_id not in conversation.seenIds:
            conversation.seenIds.append(user_id)
            await conversation.save()

        return conversation
    
    @staticmethod
    async def recall_message(message_id: str, user_id: str):
        """
        Thu hồi một tin nhắn đã gửi.
        """
        message = await Message.get(message_id)
        if not message:
            raise ValueError("Không tìm thấy tin nhắn.")

        if message.senderId != user_id:
            raise PermissionError("Bạn không có quyền thu hồi tin nhắn này.")

        # Thay đổi nội dung tin nhắn
        message.content['type'] = 'delete'
        await message.save()

        # Kiểm tra và cập nhật lastMessage trong conversation
        conversation = await Conversation.get(message.conversationId)
        if conversation and conversation.lastMessage and conversation.lastMessage.createdAt == message.createdAt:
            conversation.lastMessage.content = message.content
            await conversation.save()

        # Phát broadcast tin nhắn đã thu hồi
        message_data = map_message_to_public_dict(message)
        conversation_data = map_conversation_to_public_dict(conversation)

        tasks = [
            manager.broadcast_to_user(
                uid,
                {
                    "type": "recalled_message",
                    "payload": {
                        "conversation": conversation_data,
                        "message": message_data
                    }
                }
            )
            for uid in [p.userId for p in conversation.participants]
        ]
        await asyncio.gather(*tasks)

        return message
    
    @staticmethod
    async def delete_conversation(conversation_id: str, user_id: str):
        """
        Xóa một cuộc trò chuyện bằng cách cập nhật ParticipantInfo của người dùng.
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise ValueError("Không tìm thấy cuộc trò chuyện.")

        # Kiểm tra xem người dùng có trong danh sách participants không
        participant = next((p for p in conversation.participants if p.userId == user_id), None)
        if not participant:
            raise PermissionError("Bạn không có quyền xóa cuộc trò chuyện này.")

        # Cập nhật thời gian xóa tin nhắn cuối cùng
        participant.lastMessageDelete = datetime.utcnow() + timedelta(hours=7)
        await conversation.save()

        # Thông báo cho người dùng
        task = [ 
            manager.broadcast_to_user(
                user_id,
                {
                    "type": "conversation_deleted",
                    "payload": {"conversationId": conversation_id}
                }
            )
        ]
        await asyncio.gather(*task)


        return {"message": "Cuộc trò chuyện đã được xóa thành công."}
    
    @staticmethod
    async def update_group_name(conversation_id: str, user_id: str, new_name: str):
        """
        Cập nhật tên nhóm và tạo notification message.
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise ValueError("Không tìm thấy cuộc trò chuyện.")
        
        if not conversation.isGroup:
            raise ValueError("Đây không phải là nhóm chat.")
        
        # Lấy thông tin người thay đổi
        user = await User.get(user_id)
        old_name = conversation.name
        
        # Cập nhật tên
        conversation.name = new_name
        await conversation.save()
        
        # Tạo notification message
        await MessageService.create_notification_message(
            conversation_id=conversation_id,
            notification_type="name_changed",
            text=f"Tên nhóm đã được đặt thành {new_name}",
            metadata={"old_name": old_name, "new_name": new_name, "changed_by": user.displayName if user else ""}
        )
        
        return {"message": "Tên nhóm đã được cập nhật thành công."}
    
    @staticmethod
    async def update_group_avatar(conversation_id: str, user_id: str, avatar_url: str):
        """
        Cập nhật ảnh đại diện nhóm và tạo notification message.
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise ValueError("Không tìm thấy cuộc trò chuyện.")
        
        if not conversation.isGroup:
            raise ValueError("Đây không phải là nhóm chat.")
        
        old_avatar = conversation.avatarUrl
        
        # Cập nhật avatar
        conversation.avatarUrl = avatar_url
        await conversation.save()
        
        # Tạo notification message
        await MessageService.create_notification_message(
            conversation_id=conversation_id,
            notification_type="avatar_changed",
            text="Ảnh nhóm đã được thay đổi",
            metadata={"changed_by": user_id}
        )
        
        return {"message": "Ảnh nhóm đã được cập nhật thành công."}
    
    @staticmethod
    async def leave_group(conversation_id: str, user_id: str):
        """
        Rời khỏi nhóm và tạo notification message.
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise ValueError("Không tìm thấy cuộc trò chuyện.")
        
        if not conversation.isGroup:
            raise ValueError("Đây không phải là nhóm chat.")
        
        # Kiểm tra người dùng có trong nhóm không
        participant = next((p for p in conversation.participants if p.userId == user_id), None)
        if not participant:
            raise PermissionError("Bạn không có trong nhóm này.")
        
        # Lấy thông tin người rời
        user = await User.get(user_id)
        
        # Xóa người dùng khỏi nhóm
        conversation.participants = [p for p in conversation.participants if p.userId != user_id]
        await conversation.save()
        
        # Tạo notification message (không broadcast tự động, sẽ broadcast sau)
        notification_message = await MessageService.create_notification_message(
            conversation_id=conversation_id,
            notification_type="member_left",
            text=f"{user.displayName if user else 'Người dùng'} vừa rời khỏi nhóm",
            metadata={"user_id": user_id, "display_name": user.displayName if user else ""},
            broadcast=False  # Tắt broadcast tự động, sẽ broadcast thủ công sau
        )
        
        # Broadcast tin nhắn đến tất cả thành viên còn lại trong nhóm
        async def broadcast_member_left():
            try:
                participant_ids = [p.userId for p in conversation.participants]
                
                # Format cho MessagesScreen (expect conversation data)
                conversation_data = {
                    "id": conversation_id,
                    "lastMessage": {
                        "id": str(notification_message.id),
                        "senderId": "system",
                        "content": notification_message.content,
                        "createdAt": notification_message.createdAt.isoformat(),
                    },
                    "updatedAt": notification_message.createdAt.isoformat(),
                    "seenIds": [],
                    "participantCount": len(participant_ids),
                    "participantIds": participant_ids
                }
                
                # Format cho ChatScreen (expect message data)
                message_data = {
                    "id": str(notification_message.id),
                    "conversationId": conversation_id,
                    "senderId": "system",
                    "content": notification_message.content,
                    "avatarUrl": "",
                    "createdAt": notification_message.createdAt.isoformat(),
                }
                
                # Thêm metadata về số lượng thành viên và danh sách thành viên
                metadata = {
                    "participantCount": len(participant_ids),
                    "participantIds": participant_ids
                }
                
                await asyncio.gather(*[
                    manager.broadcast_to_user(participant_id, {
                        "type": "new_message",
                        "payload": {
                            "conversation": conversation_data,
                            "message": message_data,
                            "metadata": metadata
                        }
                    }) for participant_id in participant_ids
                ])
            except Exception as e:
                print(f"Failed to broadcast member left message: {e}")
        
        # Chạy broadcast trong background
        asyncio.create_task(broadcast_member_left())
        
        # Gửi push notification cho users offline không tắt thông báo
        async def send_push_notifications_leave():
            try:
                # Lấy danh sách participants không tắt thông báo (không phải user rời)
                participants_to_notify = [
                    p.userId for p in conversation.participants
                    if p.userId != user_id and not p.muteNotifications
                ]
                
                if not participants_to_notify:
                    return
                
                # TẠM BỎ: Gửi push notification cho tất cả users (kể cả đang online)
                # offline_user_ids = manager.get_offline_users(participants_to_notify)
                # if not offline_user_ids:
                #     return
                
                # Gửi cho tất cả participants (không phân biệt online/offline)
                offline_user_ids = participants_to_notify
                
                user_name = user.displayName if user else "Người dùng"
                group_name = conversation.name or "Nhóm"
                
                await FCMService.send_group_notification(
                    conversation_id=conversation_id,
                    notification_type="member_left",
                    title=group_name,
                    body=f"{user_name} vừa rời khỏi nhóm",
                    offline_user_ids=offline_user_ids,
                    metadata={"user_id": user_id, "user_name": user_name}
                )
            except Exception as e:
                pass
        
        asyncio.create_task(send_push_notifications_leave())
        
        return {"message": "Bạn đã rời khỏi nhóm thành công."}
    
    @staticmethod
    async def add_member_to_group(conversation_id: str, added_by: str, member_id: str):
        """
        Thêm thành viên vào nhóm và tạo notification message.
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise ValueError("Không tìm thấy cuộc trò chuyện.")
        
        if not conversation.isGroup:
            raise ValueError("Đây không phải là nhóm chat.")
        
        # Kiểm tra thành viên đã có trong nhóm chưa
        existing = next((p for p in conversation.participants if p.userId == member_id), None)
        if existing:
            raise ValueError("Thành viên này đã có trong nhóm.")
        
        # Lấy thông tin người được thêm
        member = await User.get(member_id)
        if not member:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Thêm thành viên mới
        conversation.participants.append(ParticipantInfo(userId=member_id))
        await conversation.save()
        
        # Lấy thông tin người thêm
        adder = await User.get(added_by)
        adder_name = adder.displayName if adder else "Người dùng"
        
        # Tạo 1 notification message duy nhất cho tất cả (không broadcast tự động, sẽ broadcast sau)
        notification_message = await MessageService.create_notification_message(
            conversation_id=conversation_id,
            notification_type="member_added",
            text=f"{adder_name} đã thêm {member.displayName} vào nhóm",
            metadata={"member_id": member_id, "member_name": member.displayName, "added_by": added_by},
            broadcast=False  # Tắt broadcast tự động, sẽ broadcast thủ công sau
        )
        
        # Broadcast tin nhắn đến tất cả thành viên trong nhóm
        async def broadcast_member_added():
            try:
                participant_ids = [p.userId for p in conversation.participants]
                
                # Format cho MessagesScreen (expect conversation data)
                conversation_data = {
                    "id": conversation_id,
                    "lastMessage": {
                        "id": str(notification_message.id),
                        "senderId": "system",
                        "content": notification_message.content,
                        "createdAt": notification_message.createdAt.isoformat(),
                    },
                    "updatedAt": notification_message.createdAt.isoformat(),
                    "seenIds": [],
                    "participantCount": len(participant_ids),
                    "participantIds": participant_ids
                }
                
                # Format cho ChatScreen (expect message data)
                message_data = {
                    "id": str(notification_message.id),
                    "conversationId": conversation_id,
                    "senderId": "system",
                    "content": notification_message.content,
                    "avatarUrl": "",
                    "createdAt": notification_message.createdAt.isoformat(),
                }
                
                # Thêm metadata về số lượng thành viên và danh sách thành viên
                metadata = {
                    "participantCount": len(participant_ids),
                    "participantIds": participant_ids
                }
                
                for participant_id in participant_ids:
                    await manager.broadcast_to_user(participant_id, {
                        "type": "new_message",
                        "payload": {
                            "conversation": conversation_data,
                            "message": message_data,
                            "metadata": metadata
                        }
                    })
            except Exception as e:
                print(f"Failed to broadcast member added message: {e}")
        
        # Chạy broadcast trong background
        asyncio.create_task(broadcast_member_added())
        
        # Gửi push notification cho users offline không tắt thông báo
        async def send_push_notifications_add():
            try:
                # Lấy danh sách participants không tắt thông báo (bao gồm cả member được thêm mới)
                participants_to_notify = [
                    p.userId for p in conversation.participants
                    if not p.muteNotifications
                ]
                
                if not participants_to_notify:
                    return
                
                # TẠM BỎ: Gửi push notification cho tất cả users (kể cả đang online)
                # offline_user_ids = manager.get_offline_users(participants_to_notify)
                # if not offline_user_ids:
                #     return
                
                # Gửi cho tất cả participants (không phân biệt online/offline)
                offline_user_ids = participants_to_notify
                
                group_name = conversation.name or "Nhóm"
                member_name = member.displayName if member else "Người dùng"
                
                await FCMService.send_group_notification(
                    conversation_id=conversation_id,
                    notification_type="member_added",
                    title=group_name,
                    body=f"{adder_name} đã thêm {member_name} vào nhóm",
                    offline_user_ids=offline_user_ids,
                    metadata={
                        "member_id": member_id,
                        "member_name": member_name,
                        "added_by": added_by,
                        "adder_name": adder_name
                    }
                )
            except Exception as e:
                pass
        
        asyncio.create_task(send_push_notifications_add())
        
        return {"message": "Thành viên đã được thêm vào nhóm thành công."}
    
    @staticmethod
    async def toggle_mute_notifications(conversation_id: str, user_id: str, muted: bool):
        """
        Bật/tắt thông báo cho conversation của user.
        
        Args:
            conversation_id: ID của conversation
            user_id: ID của user
            muted: True để tắt thông báo, False để bật thông báo
        """
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise ValueError("Cuộc trò chuyện không tồn tại.")
        
        # Tìm participant info của user
        participant = next(
            (p for p in conversation.participants if p.userId == user_id),
            None
        )
        
        if not participant:
            raise PermissionError("Bạn không thuộc cuộc trò chuyện này.")
        
        # Cập nhật muteNotifications
        participant.muteNotifications = muted
        await conversation.save()
        
        return {
            "message": "Đã tắt thông báo" if muted else "Đã bật thông báo",
            "muted": muted
        }
    
    @staticmethod
    async def update_group_avatar(conversation_id: str, user_id: str, avatar_file):
        """Cập nhật ảnh đại diện của nhóm."""
        try:
            conversation = await Conversation.get(conversation_id)
            if not conversation:
                raise ValueError("Cuộc trò chuyện không tồn tại")
            
            if not conversation.isGroup:
                raise ValueError("Chỉ có thể đổi ảnh nhóm")
            
            # Kiểm tra user có trong nhóm không
            participant_ids = [p.userId for p in conversation.participants]
            if user_id not in participant_ids:
                raise PermissionError("Bạn không có quyền chỉnh sửa nhóm này")
            
            # Upload ảnh mới lên Cloudinary
            from ..utils.upload_to_cloudinary import upload_to_cloudinary
            result = await upload_to_cloudinary(avatar_file, folder="group_avatars")
            avatar_url = result["url"]
            
            # Cập nhật avatar trong database
            conversation.avatarUrl = avatar_url
            await conversation.save()
            
            # Tạo notification message
            notification_message = await MessageService.create_notification_message(
                conversation_id=conversation_id,
                notification_type="avatar_changed",
                text="Ảnh nhóm đã được thay đổi",
                metadata={"changed_by": user_id}
            )
            
            # Broadcast cập nhật conversation đến tất cả thành viên
            async def broadcast_avatar_changed():
                try:
                    participant_ids = [p.userId for p in conversation.participants]
                    
                    for participant_id in participant_ids:
                        await manager.broadcast_to_user(participant_id, {
                            "type": "conversation_updated",
                            "payload": {
                                "conversation": {
                                    "id": conversation_id,
                                    "avatarUrl": avatar_url
                                }
                            }
                        })
                except Exception as e:
                    pass
            
            asyncio.create_task(broadcast_avatar_changed())
            
            return {"avatarUrl": avatar_url}
        except Exception as e:
            raise Exception(f"Không thể cập nhật ảnh nhóm: {e}")
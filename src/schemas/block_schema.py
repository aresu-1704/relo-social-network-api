from pydantic import BaseModel

class BlockUserRequest(BaseModel):
    user_id: str

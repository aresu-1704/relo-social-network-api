from bson import ObjectId
from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import OAuth2PasswordBearer
from .services import jwt_service
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

async def get_user_from_token(token: str) -> User:
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        token_data = jwt_service.decode_access_token(token)
        if not token_data or not token_data.username:
            logger.error(f"Token decode failed or missing username: {token_data}")
            raise credentials_exception

        # Kiểm tra định dạng ObjectId
        try:
            user_id = ObjectId(token_data.username)
        except Exception as e:
            logger.error(f"Invalid ObjectId format: {token_data.username}, error: {e}")
            raise credentials_exception
        
        user = await User.find_one(User.id == user_id)
        
        if user is None:
            logger.error(f"User not found with ID: {token_data.username}")
            raise credentials_exception
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_user_from_token: {e}")
        raise credentials_exception

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    return await get_user_from_token(token)

async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    user = await get_user_from_token(token)
    return str(user.id)

async def get_current_user_ws(websocket: WebSocket) -> User:

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        # The line above closes the connection, but we need to raise an exception
        # to stop further execution in the dependency chain.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token is missing")

    try:
        user = await get_user_from_token(token)
        return user
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise

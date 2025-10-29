from passlib.context import CryptContext
from ..models.user import User
from ..models.otp import OTP
from ..services.email_service import EmailService
from datetime import datetime, timedelta
import random
import re

# Thiết lập ngữ cảnh băm mật khẩu
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:

    @staticmethod
    def verify_password(plain_password, hashed_password):
        """Xác minh mật khẩu thuần túy với mật khẩu đã được băm."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password):
        """Băm một mật khẩu thuần túy."""
        return pwd_context.hash(password)

    @staticmethod
    async def register_user(username, email, password, displayName):
        """
        Xử lý đăng ký người dùng mới.
        Kiểm tra tên người dùng/email đã tồn tại, băm mật khẩu và tạo người dùng.
        """
        # Kiểm tra xem người dùng đã tồn tại chưa bằng cách truy vấn bất đồng bộ
        if await User.find_one(User.username == username):
            raise ValueError(f"Tên người dùng '{username}' đã tồn tại.")
        if await User.find_one(User.email == email):
            raise ValueError(f"Email '{email}' đã tồn tại.")

        # Băm mật khẩu (hoạt động đồng bộ)
        hashed_password = AuthService.get_password_hash(password)
        
        # Tạo một thực thể người dùng mới
        # Salt được passlib xử lý tự động và là một phần của chuỗi băm.
        new_user = User(
            username=username,
            email=email,
            hashedPassword=hashed_password,
            displayName=displayName
        )
        
        # Lưu người dùng mới vào cơ sở dữ liệu một cách bất đồng bộ
        await new_user.save()
        return new_user

    @staticmethod
    async def login_user(username, password, device_token: str = None):
        """
        Xử lý đăng nhập của người dùng.
        Tìm người dùng bằng username và xác minh mật khẩu.
        """
        # Tìm người dùng bằng username một cách bất đồng bộ
        user = await User.find_one(User.username == username)
        if not user:
            return None # Không tìm thấy người dùng
        
        # Kiểm tra nếu tài khoản đã bị xóa (soft delete)
        if user.status == 'deleted':
            raise ValueError("Tài khoản đã bị xóa. Vui lòng liên hệ hỗ trợ nếu cần khôi phục.")
        
        # Xác minh mật khẩu (hoạt động đồng bộ)
        if not AuthService.verify_password(password, user.hashedPassword):
            return None # Mật khẩu không hợp lệ
        
        # Thêm device token vào list nếu được cung cấp và chưa có trong list
        if device_token:
            if user.deviceTokens is None:
                user.deviceTokens = []
            if device_token not in user.deviceTokens:
                user.deviceTokens.append(device_token)
                await user.save()
        return user

    @staticmethod
    async def send_otp(identifier: str, require_user_exists: bool = True):
        """
        Gửi mã OTP qua email.
        
        Args:
            identifier: Username hoặc email của người dùng
            require_user_exists: Nếu True thì phải tìm thấy user, nếu False thì chỉ cần gửi OTP (dùng cho đổi email)
            
        Returns:
            dict: Thông báo thành công
            
        Raises:
            ValueError: Nếu không tìm thấy người dùng hoặc lỗi gửi email
        """
        # Kiểm tra xem identifier là email hay username
        is_email = re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', identifier)
        
        if is_email:
            # Nếu là email
            if require_user_exists:
                # Tìm user theo email
                user = await User.find_one(User.email == identifier)
                if not user:
                    raise ValueError(f"Không tìm thấy tài khoản với email '{identifier}'.")
                # Kiểm tra nếu tài khoản đã bị xóa
                if user.status == 'deleted':
                    raise ValueError("Tài khoản đã bị xóa. Vui lòng liên hệ hỗ trợ nếu cần khôi phục.")
            email = identifier
        else:
            # Nếu là username, phải tìm user theo username
            user = await User.find_one(User.username == identifier)
            if not user:
                raise ValueError(f"Không tìm thấy tài khoản với username '{identifier}'.")
            # Kiểm tra nếu tài khoản đã bị xóa
            if user.status == 'deleted':
                raise ValueError("Tài khoản đã bị xóa. Vui lòng liên hệ hỗ trợ nếu cần khôi phục.")
            email = user.email
        
        # Tạo mã OTP 6 chữ số
        otp_code = str(random.randint(100000, 999999))
        
        # Hash mã OTP
        hashed_otp = AuthService.get_password_hash(otp_code)
        
        # Thời gian hết hạn (5 phút)
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        # Vô hiệu hóa các OTP cũ của email này (chưa sử dụng)
        existing_otps = await OTP.find(
            OTP.email == email,
            OTP.is_used == False
        ).to_list()
        
        for existing_otp in existing_otps:
            existing_otp.is_used = True
            await existing_otp.save()
        
        # Lưu OTP mới vào database
        new_otp = OTP(
            email=email,
            otp_code=hashed_otp,
            expires_at=expires_at,
            is_used=False
        )
        await new_otp.save()
        
        # Gửi email
        try:
            await EmailService.send_otp_email(email, otp_code)
        except Exception as e:
            # Xóa OTP nếu không gửi được email
            await new_otp.delete()
            raise ValueError(f"Không thể gửi email: {str(e)}")
        
        return {
            "message": f"Đã gửi mã OTP đến email của bạn",
            "email": email
        }

    @staticmethod
    async def verify_otp(email: str, otp_code: str):
        """
        Xác minh mã OTP.
        
        Args:
            email: Email của người dùng
            otp_code: Mã OTP cần xác minh
            
        Returns:
            dict: Thông tin xác minh thành công
            
        Raises:
            ValueError: Nếu OTP không hợp lệ hoặc đã hết hạn
        """
        # Tìm OTP chưa sử dụng và chưa hết hạn
        current_time = datetime.utcnow()
        otp_record = await OTP.find_one(
            OTP.email == email,
            OTP.is_used == False,
            OTP.expires_at > current_time
        )
        
        if not otp_record:
            raise ValueError("Mã OTP không hợp lệ hoặc đã hết hạn. Vui lòng yêu cầu mã mới.")
        
        # Xác minh mã OTP
        if not AuthService.verify_password(otp_code, otp_record.otp_code):
            raise ValueError("Mã OTP không chính xác.")
        
        # Đánh dấu OTP đã sử dụng
        otp_record.is_used = True
        await otp_record.save()
        
        return {
            "message": "Xác minh OTP thành công",
            "email": email
        }

    @staticmethod
    async def reset_password(email: str, new_password: str):
        """
        Đặt lại mật khẩu mới cho người dùng.
        
        Args:
            email: Email của người dùng
            new_password: Mật khẩu mới
            
        Returns:
            dict: Thông báo thành công
            
        Raises:
            ValueError: Nếu không tìm thấy người dùng
        """
        # Tìm user theo email
        user = await User.find_one(User.email == email)
        if not user:
            raise ValueError(f"Không tìm thấy tài khoản với email '{email}'.")
        
        # Kiểm tra nếu tài khoản đã bị xóa
        if user.status == 'deleted':
            raise ValueError("Tài khoản đã bị xóa. Vui lòng liên hệ hỗ trợ nếu cần khôi phục.")
        
        # Băm mật khẩu mới
        hashed_password = AuthService.get_password_hash(new_password)
        
        # Cập nhật mật khẩu
        user.hashedPassword = hashed_password
        await user.save()
        
        # Vô hiệu hóa tất cả OTP của email này sau khi đổi mật khẩu thành công
        otps = await OTP.find(OTP.email == email).to_list()
        for otp in otps:
            otp.is_used = True
            await otp.save()
        
        return {
            "message": "Đặt lại mật khẩu thành công"
        }

    @staticmethod
    async def change_email_verify_password(user_id: str, new_email: str, password: str):
        """
        Xác minh mật khẩu và gửi OTP đến email mới để đổi email.
        
        Args:
            user_id: ID của người dùng
            new_email: Email mới cần đổi
            password: Mật khẩu hiện tại để xác minh
            
        Returns:
            dict: Thông báo và email
            
        Raises:
            ValueError: Nếu không tìm thấy user, mật khẩu sai, email mới đã tồn tại, hoặc lỗi gửi email
        """
        from bson import ObjectId
        
        # Tìm user theo ID
        user = await User.find_one(User.id == ObjectId(user_id))
        if not user:
            raise ValueError("Không tìm thấy tài khoản.")
        
        # Kiểm tra nếu tài khoản đã bị xóa
        if user.status == 'deleted':
            raise ValueError("Tài khoản đã bị xóa. Vui lòng liên hệ hỗ trợ nếu cần khôi phục.")
        
        # Kiểm tra nếu email mới đã được sử dụng
        existing_user = await User.find_one(User.email == new_email)
        if existing_user and str(existing_user.id) != user_id:
            raise ValueError(f"Email '{new_email}' đã được sử dụng bởi tài khoản khác.")
        
        # Xác minh mật khẩu
        if not AuthService.verify_password(password, user.hashedPassword):
            raise ValueError("Mật khẩu không chính xác.")
        
        # Gửi OTP đến email mới (không cần email phải tồn tại trong hệ thống)
        try:
            result = await AuthService.send_otp(new_email, require_user_exists=False)
            return {
                "message": "Đã gửi mã OTP xác nhận đến email mới",
                "email": new_email
            }
        except Exception as e:
            raise ValueError(f"Không thể gửi OTP đến email mới: {str(e)}")

    @staticmethod
    async def update_email(user_id: str, new_email: str):
        """
        Cập nhật email mới cho người dùng sau khi đã verify OTP.
        
        Args:
            user_id: ID của người dùng
            new_email: Email mới
            
        Returns:
            dict: Thông báo thành công
            
        Raises:
            ValueError: Nếu không tìm thấy user, email đã tồn tại
        """
        from bson import ObjectId
        
        # Tìm user theo ID
        user = await User.find_one(User.id == ObjectId(user_id))
        if not user:
            raise ValueError("Không tìm thấy tài khoản.")
        
        # Lưu email cũ
        old_email = user.email
        
        # Kiểm tra nếu email mới đã được sử dụng
        existing_user = await User.find_one(User.email == new_email)
        if existing_user and str(existing_user.id) != user_id:
            raise ValueError(f"Email '{new_email}' đã được sử dụng bởi tài khoản khác.")
        
        # Cập nhật email
        user.email = new_email
        await user.save()
        
        # Vô hiệu hóa tất cả OTP của email cũ
        old_email_otps = await OTP.find(OTP.email == old_email).to_list()
        for otp in old_email_otps:
            otp.is_used = True
            await otp.save()
        
        return {
            "message": "Đổi email thành công"
        }
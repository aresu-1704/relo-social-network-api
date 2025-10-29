import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    
    @staticmethod
    def get_email_config():
        """Lấy cấu hình email từ file .env"""
        return {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'smtp_username': os.getenv('SMTP_USERNAME'),
            'smtp_password': os.getenv('SMTP_PASSWORD'),
            'from_email': os.getenv('FROM_EMAIL')
        }
    
    @staticmethod
    async def send_otp_email(to_email: str, otp_code: str):
        """
        Gửi email chứa mã OTP đến người dùng.
        
        Args:
            to_email: Email người nhận
            otp_code: Mã OTP 6 chữ số
            
        Raises:
            Exception: Nếu không thể gửi email
        """
        config = EmailService.get_email_config()
        
        # Kiểm tra cấu hình email
        if not all([config['smtp_username'], config['smtp_password'], config['from_email']]):
            raise Exception("Cấu hình email chưa được thiết lập trong file .env")
        
        # Tạo message
        message = MIMEMultipart('alternative')
        message['Subject'] = 'Mã OTP xác thực - Relo Social Network'
        message['From'] = config['from_email']
        message['To'] = to_email
        
        # Nội dung email
        text = f"""
        Chào bạn,
        
        Mã OTP của bạn là: {otp_code}
        
        Mã này có hiệu lực trong 5 phút.
        
        Nếu bạn không yêu cầu mã này, vui lòng bỏ qua email này.
        
        Trân trọng,
        Đội ngũ Relo Social Network
        """
        
        html = f"""
        <html>
          <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
              <h2 style="color: #333;">Xác thực tài khoản Relo</h2>
              <p>Chào bạn,</p>
              <p>Mã OTP của bạn là:</p>
              <div style="background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #007bff; margin: 20px 0;">
                {otp_code}
              </div>
              <p>Mã này có hiệu lực trong <strong>5 phút</strong>.</p>
              <p style="color: #888;">Nếu bạn không yêu cầu mã này, vui lòng bỏ qua email này.</p>
              <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
              <p style="color: #888; font-size: 12px;">Trân trọng,<br>Đội ngũ Relo Social Network</p>
            </div>
          </body>
        </html>
        """
        
        # Gắn nội dung vào message
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        message.attach(part1)
        message.attach(part2)
        
        # Gửi email
        try:
            with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
                server.starttls()
                server.login(config['smtp_username'], config['smtp_password'])
                server.send_message(message)
            print(f"Đã gửi OTP đến email: {to_email}")
        except Exception as e:
            raise Exception(f"Không thể gửi email: {str(e)}")


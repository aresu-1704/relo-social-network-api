import cloudinary.uploader
from fastapi import UploadFile

async def upload_to_cloudinary(file: UploadFile, folder: str = "chat_media"):
    """
    Upload 1 file (image/video/audio) lên Cloudinary.
    Tự động xác định loại (resource_type="auto").
    """
    try:
        result = cloudinary.uploader.upload(
            file.file,
            resource_type="auto",  # cho phép image, video, audio
            folder=folder          # tùy chọn: lưu vào thư mục Cloudinary
        )
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "resource_type": result["resource_type"],
            "format": result.get("format"),
            "bytes": result.get("bytes")
        }
    except Exception as e:
        print("❌ Upload to Cloudinary failed:", e)
        raise e

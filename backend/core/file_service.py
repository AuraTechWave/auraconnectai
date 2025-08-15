import os
import uuid
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile
import logging

logger = logging.getLogger(__name__)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


class FileService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "auraconnect-attachments")
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "10485760"))
        self.allowed_extensions = {
            "pdf",
            "doc",
            "docx",
            "txt",
            "jpg",
            "jpeg",
            "png",
            "gif",
            "bmp",
        }

    async def _validate_file(self, file: UploadFile) -> None:
        content = await file.read()
        if len(content) > self.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of "
                f"{self.max_file_size} bytes",
            )
        await file.seek(0)
        if file.filename:
            extension = file.filename.split(".")[-1].lower()
            if extension not in self.allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{extension}' not allowed. "
                    f"Allowed: {', '.join(self.allowed_extensions)}",
                )

    async def upload_file(self, file: UploadFile, folder: str = "orders") -> dict:
        try:
            await self._validate_file(file)
            file_id = str(uuid.uuid4())
            file_extension = file.filename.split(".")[-1] if file.filename else "bin"
            s3_key = f"{folder}/{file_id}.{file_extension}"
            file_content = await file.read()
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=file.content_type or "application/octet-stream",
            )
            file_url = f"https://{self.bucket_name}.s3.amazonaws.com/" f"{s3_key}"
            return {
                "file_url": file_url,
                "file_name": (file.filename or f"{file_id}.{file_extension}"),
                "file_type": (file.content_type or "application/octet-stream"),
                "file_size": len(file_content),
            }
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to upload file to storage"
            )
        except Exception as e:
            logger.error(f"File upload error: {e}")
            raise HTTPException(status_code=500, detail="Failed to process file upload")

    def delete_file(self, file_url: str) -> bool:
        try:
            s3_key = file_url.split(f"{self.bucket_name}.s3.amazonaws.com/")[-1]
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            logger.error(f"S3 delete error: {e}")
            return False
        except Exception as e:
            logger.error(f"File delete error: {e}")
            return False

    def get_presigned_url(self, file_url: str, expiration: int = 3600) -> Optional[str]:
        try:
            s3_key = file_url.split(f"{self.bucket_name}.s3.amazonaws.com/")[-1]
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
            return presigned_url
        except ClientError as e:
            logger.error(f"S3 presigned URL error: {e}")
            return None
        except Exception as e:
            logger.error(f"Presigned URL error: {e}")
            return None


file_service = FileService()

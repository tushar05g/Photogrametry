import boto3
import json
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from botocore.exceptions import ClientError
from storage.provider import StorageProvider
from backend.config import settings
import io

logger = logging.getLogger(__name__)

class S3StorageProvider(StorageProvider):
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION
        )
        self.bucket = settings.S3_BUCKET

    def upload_file(self, path: str, data: Union[bytes, Path, str]) -> str:
        try:
            if isinstance(data, (str, Path)):
                self.s3_client.upload_file(str(data), self.bucket, path)
            else:
                self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=data)
            logger.info(f"Uploaded to {path}")
            return path
        except ClientError as e:
            logger.error(f"Failed to upload to {path}: {e}")
            raise

    def download_file(self, path: str, local_path: Optional[Path] = None) -> Union[bytes, Path]:
        try:
            if local_path:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self.s3_client.download_file(self.bucket, path, str(local_path))
                return local_path
            else:
                response = self.s3_client.get_object(Bucket=self.bucket, Key=path)
                return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to download {path}: {e}")
            raise

    def put_json(self, path: str, data: Dict[str, Any]):
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=path,
                Body=json.dumps(data),
                ContentType="application/json"
            )
        except ClientError as e:
            logger.error(f"Failed to put JSON to {path}: {e}")
            raise

    def get_json(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=path)
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            logger.error(f"Failed to get JSON from {path}: {e}")
            raise

    def generate_signed_url(self, path: str, expires_in: int = 3600) -> str:
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": path},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate signed URL for {path}: {e}")
            raise

    def list_files(self, path: str) -> List[str]:
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=path)
            files = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        files.append(obj["Key"])
            return files
        except ClientError as e:
            logger.error(f"Failed to list files with prefix {path}: {e}")
            raise

    def delete_file(self, path: str):
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=path)
        except ClientError as e:
            logger.error(f"Failed to delete {path}: {e}")
            raise

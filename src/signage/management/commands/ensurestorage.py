"""Create the object storage bucket and let browsers read from it.

Runs before `collectstatic` in the Compose `setup` service. MinIO ships no bucket, and the
admin's static files and the uploaded background are fetched by browsers without
credentials, so the bucket gets an anonymous `s3:GetObject` policy. Idempotent.
"""

from __future__ import annotations

import json

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.storage import storages
from django.core.management.base import BaseCommand


def read_only_policy(bucket: str) -> str:
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"],
                }
            ],
        }
    )


class Command(BaseCommand):
    help = "Create the storage bucket and allow anonymous reads of its objects."

    def handle(self, *args, **options):
        if not settings.STORAGE.enabled:
            self.stdout.write("Object storage is not configured; files stay on disk.")
            return
        storage = storages["staticfiles"]
        client = storage.connection.meta.client
        bucket = storage.bucket_name
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
                raise
            client.create_bucket(Bucket=bucket)
            self.stdout.write(f"Created bucket {bucket}.")
        client.put_bucket_policy(Bucket=bucket, Policy=read_only_policy(bucket))
        self.stdout.write(f"Bucket {bucket} is ready; objects are readable anonymously.")

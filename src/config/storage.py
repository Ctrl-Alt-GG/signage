"""File storage wiring: an S3 bucket (MinIO in the Compose stack) when an endpoint is
configured, the local filesystem otherwise. Shared by the settings and `ensurestorage`."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

FILESYSTEM = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@dataclass(frozen=True)
class ObjectStorage:
    enabled: bool
    bucket: str
    storages: dict
    static_url: str
    media_url: str


def object_storage(
    *,
    endpoint_url: str,
    public_url: str,
    bucket: str,
    access_key: str,
    secret_key: str,
    region: str,
) -> ObjectStorage:
    """Build the STORAGES mapping and the browser-facing URL prefixes.

    `endpoint_url` is where the backend talks to the bucket (inside the Compose network);
    `public_url` is where browsers reach the same bucket, which may include a path when a
    reverse proxy mounts the store under a prefix. Both static files and uploads share one
    bucket under the `static/` and `media/` prefixes, so one anonymous-read policy covers them.
    """
    if not endpoint_url:
        return ObjectStorage(False, bucket, FILESYSTEM, "/static/", "/media/")
    public = urlsplit((public_url or endpoint_url).rstrip("/"))
    custom_domain = f"{public.netloc}{public.path}/{bucket}"
    common = {
        "access_key": access_key,
        "secret_key": secret_key,
        "bucket_name": bucket,
        "endpoint_url": endpoint_url,
        "region_name": region,
        "addressing_style": "path",
        "signature_version": "s3v4",
        "custom_domain": custom_domain,
        "url_protocol": f"{public.scheme}:",
        "querystring_auth": False,
    }
    base = f"{public.scheme}://{custom_domain}"
    return ObjectStorage(
        enabled=True,
        bucket=bucket,
        storages={
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": {**common, "location": "media"},
            },
            "staticfiles": {
                "BACKEND": "storages.backends.s3.S3StaticStorage",
                "OPTIONS": {
                    **common,
                    "location": "static",
                    "object_parameters": {"CacheControl": "public, max-age=3600"},
                },
            },
        },
        static_url=f"{base}/static/",
        media_url=f"{base}/media/",
    )

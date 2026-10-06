from io import StringIO

from django.core.management import call_command
from storages.backends.s3 import S3StaticStorage

from config.storage import object_storage


def test_filesystem_without_an_endpoint():
    storage = object_storage(
        endpoint_url="", public_url="", bucket="signage", access_key="", secret_key="", region="r"
    )
    assert not storage.enabled
    assert storage.static_url == "/static/" and storage.media_url == "/media/"
    assert storage.storages["staticfiles"]["BACKEND"].endswith(".StaticFilesStorage")


def test_bucket_urls_follow_the_public_url():
    storage = object_storage(
        endpoint_url="http://minio:9000",
        public_url="https://signage.example/s3",
        bucket="signage",
        access_key="key",
        secret_key="secret",
        region="us-east-1",
    )
    assert storage.enabled
    assert storage.static_url == "https://signage.example/s3/signage/static/"
    assert storage.media_url == "https://signage.example/s3/signage/media/"
    options = storage.storages["staticfiles"]["OPTIONS"]
    assert options["endpoint_url"] == "http://minio:9000"
    assert options["location"] == "static"
    assert storage.storages["default"]["OPTIONS"]["location"] == "media"
    # django-storages composes the browser URL from these options without touching the network.
    url = S3StaticStorage(**options).url("admin/css/base.css")
    assert url == "https://signage.example/s3/signage/static/admin/css/base.css"


def test_public_url_defaults_to_the_endpoint():
    storage = object_storage(
        endpoint_url="http://localhost:9000",
        public_url="",
        bucket="signage",
        access_key="key",
        secret_key="secret",
        region="us-east-1",
    )
    assert storage.static_url == "http://localhost:9000/signage/static/"


def test_ensurestorage_is_a_no_op_on_disk():
    out = StringIO()
    call_command("ensurestorage", stdout=out)
    assert "not configured" in out.getvalue()

#!/usr/bin/env python3
"""
Upload a local image to MinIO and trigger your Django ingest endpoint using image_uri.

Reads configuration from a .env file in the current working directory.
Required env vars (typical values shown):

MINIO_ENDPOINT=http://localhost:9000        # S3 API endpoint (or http://minio:9000 if running inside Docker network)
MINIO_ACCESS_KEY=minioaccess
MINIO_SECRET_KEY=miniosecret
MINIO_BUCKET=receipts
MINIO_REGION=us-east-1

# Choose how image_uri is formed:
#   presigned  -> generate a time-limited URL (bucket can stay private)
#   public     -> build a public URL "<MINIO_PUBLIC_BASE or MINIO_ENDPOINT>/<bucket>/<key>" (bucket must allow anonymous GET)
IMAGE_URL_MODE=presigned                    # or: public
MINIO_PUBLIC_BASE=http://localhost:9000     # optional; used only when IMAGE_URL_MODE=public

DJANGO_API_BASE=http://localhost:8000
INGEST_PATH=/api/v1/receipt/ingest
# DJANGO_AUTH_TOKEN=...                     # optional
# KEY_PREFIX=YYYY/MM/DD                     # optional; default is today's date
# URL_EXPIRES=900                           # optional; seconds for presigned URL
# IDEMPOTENCY_KEY=...                       # optional; default random UUID
"""

import argparse
import os
import sys
import uuid
import mimetypes
from datetime import datetime

import requests
from dotenv import load_dotenv
import boto3
from botocore.client import Config


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"[config] Missing required env var: {name}", file=sys.stderr)
        sys.exit(2)
    return val


def guess_content_type(path: str) -> str:
    ctype, _ = mimetypes.guess_type(path)
    return ctype or "application/octet-stream"


def build_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=require_env("MINIO_ENDPOINT"),
        aws_access_key_id=require_env("MINIO_ACCESS_KEY"),
        aws_secret_access_key=require_env("MINIO_SECRET_KEY"),
        region_name=os.getenv("MINIO_REGION", "us-east-1"),
        config=Config(signature_version="s3v4"),
    )


def make_key(filename: str) -> str:
    prefix = os.getenv("KEY_PREFIX") or datetime.utcnow().strftime("%Y/%m/%d")
    return f"{prefix}/{uuid.uuid4()}-{filename}"


def upload_file(s3, bucket: str, local_path: str, key: str):
    extra = {"ContentType": guess_content_type(local_path)}
    s3.upload_file(local_path, bucket, key, ExtraArgs=extra)


def public_url(bucket: str, key: str) -> str:
    base = os.getenv("MINIO_PUBLIC_BASE") or require_env("MINIO_ENDPOINT")
    return f"{base.rstrip('/')}/{bucket}/{key}"


def presigned_url(s3, bucket: str, key: str) -> str:
    expires = int(os.getenv("URL_EXPIRES", "900"))
    # NOTE: Presigned URL host must be reachable by Django.
    # If Django runs in Docker, MINIO_ENDPOINT should usually be http://minio:9000.
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires
    )


def call_ingest(image_uri: str):
    base = require_env("DJANGO_API_BASE").rstrip("/")
    path = os.getenv("INGEST_PATH", "/api/v1/receipt/ingest")
    url = f"{base}{path}"
    idem = os.getenv("IDEMPOTENCY_KEY", str(uuid.uuid4()))
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": idem,
    }
    token = os.getenv("DJANGO_AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.post(url, json={"image_uri": image_uri}, headers=headers, timeout=60)
    return resp


def main():
    load_dotenv()  # load .env from CWD

    parser = argparse.ArgumentParser(description="Upload image to MinIO and ingest via Django API")
    parser.add_argument("image_path", help="Path to the local image file")
    args = parser.parse_args()

    if not os.path.isfile(args.image_path):
        print(f"[error] File not found: {args.image_path}", file=sys.stderr)
        sys.exit(1)

    bucket = require_env("MINIO_BUCKET")
    mode = os.getenv("IMAGE_URL_MODE", "presigned").lower()
    if mode not in ("presigned", "public"):
        print("[config] IMAGE_URL_MODE must be 'presigned' or 'public'", file=sys.stderr)
        sys.exit(2)

    s3 = build_s3_client()
    key = make_key(os.path.basename(args.image_path))

    try:
        upload_file(s3, bucket, args.image_path, key)
    except Exception as e:
        print(f"[upload] Failed: {e}", file=sys.stderr)
        sys.exit(1)

    if mode == "public":
        image_uri = public_url(bucket, key)
    else:
        try:
            image_uri = presigned_url(s3, bucket, key)
        except Exception as e:
            print(f"[presign] Failed: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"[ok] Uploaded s3://{bucket}/{key}")
    print(f"[ok] image_uri => {image_uri}")

    try:
        resp = call_ingest(image_uri)
    except Exception as e:
        print(f"[ingest] Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[api] {resp.status_code}")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)

    # Non-2xx should be treated as failure for CI use
    if not (200 <= resp.status_code < 300):
        sys.exit(1)


if __name__ == "__main__":
    main()

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
# JOB_STATUS_PATH=/api/v1/jobs/{job_id}/    # optional; format string for job polling
# JOB_AUTO_POLL=true                        # optional; auto-enable --poll
# JOB_POLL_INTERVAL=2.0                     # optional; seconds between polls
# JOB_POLL_TIMEOUT=300                      # optional; max seconds to wait (0 = no limit)
# UPLOAD_VERBOSE=1                          # optional; auto-enable --verbose
"""

import argparse
import mimetypes
import os
import sys
import time
import uuid
from datetime import datetime

import boto3
import requests
from botocore.client import Config
from dotenv import load_dotenv


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


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        print(f"[config] Invalid float for {name}: {val}", file=sys.stderr)
        return default


def _build_job_status_url(job_id: int) -> str:
    base = require_env("DJANGO_API_BASE").rstrip("/")
    template = os.getenv("JOB_STATUS_PATH", "/api/v1/jobs/{job_id}/")
    if "{job_id}" in template:
        path = template.format(job_id=job_id)
    else:
        path = f"{template.rstrip('/')}/{job_id}/"
    return f"{base}{path}"


def _sanitize_headers(headers: dict) -> dict:
    redacted = {}
    for key, value in headers.items():
        redacted[key] = "***" if key.lower() == "authorization" else value
    return redacted


def call_ingest(image_uri: str, *, verbose: bool = False):
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

    if verbose:
        print(f"[api] POST {url}")
        print(f"[api] headers={_sanitize_headers(headers)}")
        print(f"[api] payload={{'image_uri': '{image_uri}'}}")

    resp = requests.post(url, json={"image_uri": image_uri}, headers=headers, timeout=60)
    return resp


def poll_job(job_id: int, *, interval: float, timeout: float, verbose: bool = False):
    url = _build_job_status_url(job_id)
    deadline = time.time() + timeout if timeout > 0 else None
    headers = {}
    token = os.getenv("DJANGO_AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"[job] Monitoring job {job_id} at {url}")
    while True:
        try:
            if verbose:
                print(f"[job] GET {url}")
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"[job] poll error: {exc}", file=sys.stderr)
            if deadline and time.time() >= deadline:
                print("[job] polling timed out", file=sys.stderr)
                return None
            time.sleep(interval)
            continue

        status = data.get("status") or "UNKNOWN"
        print(f"[job] status={status}")
        if verbose:
            print(f"[job] payload={data}")

        if status in {"SUCCEEDED", "FAILED"}:
            return data

        if deadline and time.time() >= deadline:
            print("[job] polling timed out", file=sys.stderr)
            return data

        time.sleep(interval)


def main():
    load_dotenv()  # load .env from CWD 

    parser = argparse.ArgumentParser(description="Upload image to MinIO and ingest via Django API")
    parser.add_argument("image_path", help="Path to the local image file")
    auto_poll = _env_bool("JOB_AUTO_POLL", False)
    parser.add_argument(
        "--poll",
        dest="poll",
        action="store_true",
        default=auto_poll,
        help="Poll the job status until it finishes (default via JOB_AUTO_POLL)",
    )
    parser.add_argument(
        "--no-poll",
        dest="poll",
        action="store_false",
        help="Disable job polling even if enabled by JOB_AUTO_POLL",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=_env_float("JOB_POLL_INTERVAL", 2.0),
        help="Seconds between job status checks (default 2, override with JOB_POLL_INTERVAL)",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=_env_float("JOB_POLL_TIMEOUT", 300.0),
        help="Time limit in seconds for polling; 0 disables timeout (default 300)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=_env_bool("UPLOAD_VERBOSE", False),
        help="Print request details and verbose polling output",
    )
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
        resp = call_ingest(image_uri, verbose=args.verbose)
    except Exception as e:
        print(f"[ingest] Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[api] {resp.status_code}")
    try:
        resp_payload = resp.json()
        print(resp_payload)
    except Exception:
        resp_payload = None
        print(resp.text)

    # Non-2xx should be treated as failure for CI use
    if not (200 <= resp.status_code < 300):
        sys.exit(1)

    if args.poll and resp_payload and isinstance(resp_payload, dict):
        job_id = resp_payload.get("id")
        if job_id is None:
            print("[job] Response did not include a job id; skipping polling", file=sys.stderr)
        else:
            result = poll_job(
                int(job_id),
                interval=max(args.poll_interval, 0.1),
                timeout=args.poll_timeout,
                verbose=args.verbose,
            )
            if result:
                status = result.get("status")
                if status == "FAILED":
                    print("[job] Job reported failure", file=sys.stderr)
                    print(result)
                    sys.exit(1)
                if status == "SUCCEEDED":
                    receipt_id = result.get("receipt")
                    if receipt_id is not None:
                        print(f"[job] Receipt created with id={receipt_id}")
            elif args.poll_timeout > 0:
                print("[job] Polling ended without a terminal status", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()

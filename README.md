# PennyWise
A backend service that uses LLM models to analyse receipts and categorise the receipt items

Endpoints: /api/v1/healthz, /api/v1/receipts/ingest, /api/v1/jobs, /api/v1/receipts
Docs: /api/docs

Quick start:
  cp .env.example .env
  docker compose up --build

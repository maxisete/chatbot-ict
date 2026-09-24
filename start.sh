#!/bin/bash
echo "=== Iniciando ingesta de documentos ==="
python src/ingestion/ingest.py
echo "=== Ingesta completada. Iniciando API ==="
uvicorn src.api.main:app --host 0.0.0.0 --port 7860

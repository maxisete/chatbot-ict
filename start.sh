#!/bin/bash
echo "=== Iniciando ingesta de documentos ==="
python src/ingestion/ingest.py
echo "=== Ingesta completada. Iniciando bot de Telegram en background ==="
python src/bot/telegram_bot.py &
BOT_PID=$!
echo "=== Bot arrancado con PID $BOT_PID. Iniciando API ==="
uvicorn src.api.main:app --host 0.0.0.0 --port 7860

#!/bin/bash
# Script de arranque del chatbot ICT

cd /home/maxi/chatbot-ict
source venv/bin/activate

echo "Arrancando API FastAPI..."
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

sleep 5

echo "Arrancando bot de Telegram..."
python src/bot/telegram_bot.py &
BOT_PID=$!

echo ""
echo "✓ Chatbot ICT corriendo."
echo "  API:     http://127.0.0.1:8000"
echo "  Telegram: @asistente_ict_bot"
echo ""
echo "Para parar todo: kill $API_PID $BOT_PID"
echo "O pulsa Ctrl+C"

wait

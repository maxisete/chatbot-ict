#!/bin/bash
# Script de arranque del chatbot ICT

cd /home/maxi/chatbot-ict
source venv/bin/activate

echo "Parando procesos anteriores si los hay..."
pkill -f "uvicorn src.api.main" 2>/dev/null
pkill -f "telegram_bot.py" 2>/dev/null
sleep 2

echo "Arrancando API FastAPI..."
nohup uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > logs/uvicorn.log 2>&1 &
echo "  PID API: $!"

sleep 5

echo "Arrancando bot de Telegram..."
nohup python src/bot/telegram_bot.py > logs/telegram.log 2>&1 &
echo "  PID Bot: $!"

echo ""
echo "✓ Chatbot ICT corriendo en segundo plano."
echo "  API:      http://127.0.0.1:8000"
echo "  Telegram: @asistente_ict_bot"
echo ""
echo "  Logs en tiempo real:"
echo "    tail -f logs/uvicorn.log"
echo "    tail -f logs/telegram.log"
echo ""
echo "  Para parar todo:"
echo "    pkill -f uvicorn && pkill -f telegram_bot.py"

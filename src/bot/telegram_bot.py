import os
import logging
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = "http://127.0.0.1:8000/consulta"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola, soy el Asistente ICT.\n\n"
        "Puedo responder preguntas sobre normativa española de "
        "Infraestructuras Comunes de Telecomunicaciones (ICT):\n"
        "• R.D. 346/2011\n"
        "• Orden ECE/983/2019\n"
        "• Reglamento ICT2 de Televés\n\n"
        "Escríbeme tu consulta y te respondo citando la fuente.\n\n"
        "⚠️ Las respuestas son orientativas. Consulta siempre la normativa oficial para proyectos reales."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💡 Ejemplos de preguntas:\n\n"
        "• ¿Qué dimensiones mínimas tiene un RITU para 25 PAU?\n"
        "• ¿Qué clase de reacción al fuego deben tener los cables coaxiales?\n"
        "• ¿Qué es el PAU?\n"
        "• ¿Cuántas tomas mínimas debe haber en el salón de una vivienda?\n"
        "• ¿Qué diferencia hay entre RITI y RITS?"
    )

async def consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    logger.info(f"Telegram consulta de {update.effective_user.username}: {pregunta}")

    await update.message.reply_text("🔍 Consultando normativa, un momento...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                API_URL,
                json={"pregunta": pregunta}
            )
            data = response.json()

        respuesta = data["respuesta"]
        fragmentos = data["fragmentos_usados"]

        docs = list(set(f["documento"] for f in fragmentos))
        fuentes = "📄 Fuentes: " + ", ".join(docs)

        mensaje_final = f"{respuesta}\n\n{fuentes}"

        if len(mensaje_final) > 4096:
            mensaje_final = mensaje_final[:4090] + "..."

        await update.message.reply_text(mensaje_final)

    except httpx.TimeoutException:
        await update.message.reply_text("⏱️ La consulta ha tardado demasiado. Inténtalo de nuevo.")
    except Exception as e:
        logger.error(f"Error en consulta Telegram: {e}")
        await update.message.reply_text("❌ Ha ocurrido un error. Inténtalo de nuevo.")

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no está configurado en .env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, consulta))

    logger.info("Bot de Telegram arrancando...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

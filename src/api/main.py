import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from collections import defaultdict
from dotenv import load_dotenv
import time
import httpx
from src.api.logging_config import setup_logging, log_consulta
from sentence_transformers import SentenceTransformer
import chromadb
from groq import Groq

# --- Configuración ---
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

VECTORDB_DIR = Path("data/vectordb")
COLLECTION_NAME = "normativa_ict"
EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"
N_RESULTADOS = 5
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://maxisete-chatbot-ict.hf.space/webhook")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SYSTEM_PROMPT = """Eres un asistente experto en normativa española de
Infraestructuras Comunes de Telecomunicaciones (ICT).

Responde ÚNICAMENTE basándote en los fragmentos de normativa que se te
proporcionan como contexto. Sigue estas reglas estrictamente:

1. JERARQUÍA DE FUENTES (obligatorio):
   - Usa SIEMPRE primero el R.D. 346/2011 y la Orden ECE/983/2019 (normativa oficial vinculante).
   - El Reglamento ICT2 de Televés es documentación técnica complementaria.
     Úsalo SOLO si la normativa oficial no contiene información suficiente.
   - Si usas Televés como complemento, indícalo explícitamente:
     "Complementando con el Reglamento ICT2 de Televés..."

2. Cita siempre el documento fuente y el apartado cuando sea posible.

3. Si la respuesta requiere interpretación más allá del texto literal,
   indícalo con: "⚠️ Orientativo:".

4. Si la información no está en ninguna de las fuentes proporcionadas,
   responde: "No dispongo de información suficiente en la normativa
   disponible para responder a esta pregunta."

5. Responde siempre en español.

6. INTERPRETACIÓN DE LA PREGUNTA: El usuario puede escribir con faltas
   de ortografía, sin tildes, sin signos de interrogación de apertura
   (¿), o con typos. Interpreta su intención de forma flexible y
   responde a lo que claramente quiere preguntar, sin pedirle que
   reformule.

7. Sé preciso y conciso. Para valores numéricos presenta los datos
   en formato tabla cuando sea posible."""

# --- Modelos globales ---
modelo_embeddings = None
coleccion_chromadb = None
cliente_groq = None
historial_conversaciones = defaultdict(list)
MAX_HISTORIAL = 6

@asynccontextmanager
async def lifespan(app: FastAPI):
    global modelo_embeddings, coleccion_chromadb, cliente_groq, telegram_app
    logger.info("Cargando modelo de embeddings...")
    modelo_embeddings = SentenceTransformer(EMBEDDING_MODEL)
    logger.info("Conectando a ChromaDB...")
    cliente_chroma = chromadb.PersistentClient(path=str(VECTORDB_DIR))
    coleccion_chromadb = cliente_chroma.get_collection(COLLECTION_NAME)
    logger.info(f"Colección cargada: {coleccion_chromadb.count()} fragmentos")
    logger.info("Conectando a Groq...")
    cliente_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
    logger.info("API lista.")


    yield

# --- Aplicación FastAPI ---
app = FastAPI(
    title="Chatbot ICT",
    description="Asistente IA para consultas sobre normativa ICT española",
    version="0.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modelos de datos ---
class PreguntaRequest(BaseModel):
    pregunta: str
    session_id: str = "web_default"

class RespuestaResponse(BaseModel):
    respuesta: str
    fragmentos_usados: list[dict]

# --- Función central de consulta (compartida web y Telegram) ---
def procesar_consulta(pregunta: str, session_id: str) -> dict:
    inicio = time.time()
    embedding = modelo_embeddings.encode(pregunta).tolist()

    resultados_oficiales = coleccion_chromadb.query(
        query_embeddings=[embedding],
        n_results=N_RESULTADOS,
        where={"prioridad": 1}
    )

    fragmentos = []
    contexto = ""

    for doc, meta in zip(resultados_oficiales["documents"][0], resultados_oficiales["metadatas"][0]):
        fragmentos.append({
            "documento": meta["documento"],
            "chunk_id": meta["chunk_id"],
            "texto": doc[:200]
        })
        contexto += f"\n---\nFuente OFICIAL: {meta['documento']}\n{doc}\n"

    if len(resultados_oficiales["documents"][0]) < 2:
        resultados_televes = coleccion_chromadb.query(
            query_embeddings=[embedding],
            n_results=2,
            where={"prioridad": 2}
        )
        for doc, meta in zip(resultados_televes["documents"][0], resultados_televes["metadatas"][0]):
            fragmentos.append({
                "documento": meta["documento"],
                "chunk_id": meta["chunk_id"],
                "texto": doc[:200]
            })
            contexto += f"\n---\nFuente COMPLEMENTARIA: {meta['documento']}\n{doc}\n"

    historial = historial_conversaciones[session_id]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(historial)
    messages.append({
        "role": "user",
        "content": f"Contexto normativo:\n{contexto}\n\nPregunta: {pregunta}"
    })

    respuesta_groq = cliente_groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.1,
        max_tokens=1024
    )
    respuesta_texto = respuesta_groq.choices[0].message.content

    historial_conversaciones[session_id].append({"role": "user", "content": pregunta})
    historial_conversaciones[session_id].append({"role": "assistant", "content": respuesta_texto})
    if len(historial_conversaciones[session_id]) > MAX_HISTORIAL * 2:
        historial_conversaciones[session_id] = historial_conversaciones[session_id][-MAX_HISTORIAL * 2:]

    duracion = int((time.time() - inicio) * 1000)
    logger.info(f"Respuesta generada ({len(respuesta_texto)} chars, {duracion}ms)")
    log_consulta(pregunta, respuesta_texto, fragmentos, duracion)

    return {"respuesta": respuesta_texto, "fragmentos_usados": fragmentos}

# --- Endpoints ---
app.mount("/static", StaticFiles(directory="src/api/static"), name="static")

@app.get("/")
def raiz():
    return FileResponse("src/api/static/index.html")

@app.get("/health")
def health():
    return {
        "estado": "ok",
        "fragmentos_indexados": coleccion_chromadb.count(),
        "bot_activo": TELEGRAM_TOKEN is not None
    }

@app.post("/consulta", response_model=RespuestaResponse)
def consultar(request: PreguntaRequest):
    if not request.pregunta.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")
    logger.info(f"Consulta web recibida: {request.pregunta}")
    resultado = procesar_consulta(request.pregunta, request.session_id)
    return RespuestaResponse(**resultado)


@app.post("/webhook")
async def webhook(request: Request):
    if not TELEGRAM_TOKEN:
        raise HTTPException(status_code=503, detail="Bot no configurado")
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    if not chat_id or not text:
        return JSONResponse(content={"ok": True})
    if text.startswith("/start"):
        respuesta = (
            "👋 Hola, soy el Asistente ICT.\n\n"
            "Puedo responder preguntas sobre normativa española de "
            "Infraestructuras Comunes de Telecomunicaciones (ICT):\n"
            "• R.D. 346/2011\n"
            "• Orden ECE/983/2019\n"
            "• Reglamento ICT2 de Televés\n\n"
            "Escríbeme tu consulta y te respondo citando la fuente.\n\n"
            "⚠️ Las respuestas son orientativas. Consulta siempre la normativa oficial para proyectos reales."
        )
    elif text.startswith("/help"):
        respuesta = (
            "💡 Ejemplos de preguntas:\n\n"
            "• ¿Qué dimensiones mínimas tiene un RITU para 25 PAU?\n"
            "• ¿Qué clase de reacción al fuego deben tener los cables coaxiales?\n"
            "• ¿Qué es el PAU?\n"
            "• ¿Cuántas tomas mínimas debe haber en el salón de una vivienda?\n"
            "• ¿Qué diferencia hay entre RITI y RITS?"
        )
    else:
        session_id = f"telegram_{chat_id}"
        try:
            resultado = procesar_consulta(text, session_id)
            respuesta_texto = resultado["respuesta"]
            fragmentos = resultado["fragmentos_usados"]
            docs = list(set(f["documento"] for f in fragmentos))
            fuentes = "📄 Fuentes: " + ", ".join(docs)
            respuesta = f"{respuesta_texto}\n\n{fuentes}"
            if len(respuesta) > 4096:
                respuesta = respuesta[:4090] + "..."
        except Exception as e:
            logger.error(f"Error procesando consulta Telegram: {e}")
            respuesta = "❌ Ha ocurrido un error. Inténtalo de nuevo."
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": respuesta}
        )
    return JSONResponse(content={"ok": True})

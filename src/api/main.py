import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from collections import defaultdict
from dotenv import load_dotenv
import time
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

6. Sé preciso y conciso. Para valores numéricos presenta los datos 
   en formato tabla cuando sea posible."""

# --- Modelos globales (se cargan una vez al arrancar) ---
modelo_embeddings = None
coleccion_chromadb = None
cliente_groq = None
historial_conversaciones = defaultdict(list)
MAX_HISTORIAL = 6  # máximo de mensajes a recordar (3 intercambios)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga los modelos al arrancar la API."""
    global modelo_embeddings, coleccion_chromadb, cliente_groq
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
    version="0.1.0",
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

# --- Endpoints ---
app.mount("/static", StaticFiles(directory="src/api/static"), name="static")
@app.get("/")
def raiz():
    return FileResponse("src/api/static/index.html")

@app.get("/health")
def health():
    return {
        "estado": "ok",
        "fragmentos_indexados": coleccion_chromadb.count()
    }

@app.post("/consulta", response_model=RespuestaResponse)
def consultar(request: PreguntaRequest):
    if not request.pregunta.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")

    logger.info(f"Consulta recibida: {request.pregunta}")

    inicio = time.time()

    # 1. Buscar fragmentos con jerarquía de fuentes
    embedding = modelo_embeddings.encode(request.pregunta).tolist()

    # Primero buscar SOLO en fuentes oficiales (prioridad 1)
    resultados_oficiales = coleccion_chromadb.query(
        query_embeddings=[embedding],
        n_results=N_RESULTADOS,
        where={"prioridad": 1}
    )

    fragmentos = []
    contexto = ""

    # Usar fuentes oficiales
    for doc, meta in zip(resultados_oficiales["documents"][0], resultados_oficiales["metadatas"][0]):
        fragmentos.append({
            "documento": meta["documento"],
            "chunk_id": meta["chunk_id"],
            "texto": doc[:200]
        })
        contexto += f"\n---\nFuente OFICIAL: {meta['documento']}\n{doc}\n"

    # Solo si hay menos de 2 fragmentos oficiales relevantes, añadir Televés
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

    # 2. Construir prompt y llamar a Groq
    # Recuperar historial de esta sesión
    historial = historial_conversaciones[request.session_id]

    # Construir messages con historial
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(historial)
    messages.append({
        "role": "user",
        "content": f"Contexto normativo:\n{contexto}\n\nPregunta: {request.pregunta}"
    })

    respuesta_groq = cliente_groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.1,
        max_tokens=1024
    )

    respuesta_texto = respuesta_groq.choices[0].message.content

    # Actualizar historial
    historial_conversaciones[request.session_id].append({
        "role": "user", "content": request.pregunta
    })
    historial_conversaciones[request.session_id].append({
        "role": "assistant", "content": respuesta_texto
    })

    # Limitar tamaño del historial
    if len(historial_conversaciones[request.session_id]) > MAX_HISTORIAL * 2:
        historial_conversaciones[request.session_id] = historial_conversaciones[request.session_id][-MAX_HISTORIAL * 2:]

    duracion = int((time.time() - inicio) * 1000)
    logger.info(f"Respuesta generada ({len(respuesta_texto)} chars, {duracion}ms)")
    log_consulta(request.pregunta, respuesta_texto, fragmentos, duracion)

    return RespuestaResponse(
        respuesta=respuesta_texto,
        fragmentos_usados=fragmentos
    )

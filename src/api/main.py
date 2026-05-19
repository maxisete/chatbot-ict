import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

1. Cita siempre el documento fuente (por ejemplo: "Según el R.D. 346/2011...").
2. Si la respuesta requiere interpretación o cálculo más allá del texto literal, 
   indícalo claramente con: "⚠️ Orientativo:".
3. Si la información no está en el contexto proporcionado, responde exactamente: 
   "No dispongo de información suficiente en la normativa disponible para 
   responder a esta pregunta."
4. Responde siempre en español.
5. Sé preciso y conciso. Para valores numéricos (dimensiones, niveles, etc.), 
   presenta los datos en formato tabla cuando sea posible."""

# --- Modelos globales (se cargan una vez al arrancar) ---
modelo_embeddings = None
coleccion_chromadb = None
cliente_groq = None

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

    # 1. Buscar fragmentos relevantes
    inicio = time.time()
    embedding = modelo_embeddings.encode(request.pregunta).tolist()
    resultados = coleccion_chromadb.query(
        query_embeddings=[embedding],
        n_results=N_RESULTADOS
    )

    fragmentos = []
    contexto = ""
    for doc, meta in zip(resultados["documents"][0], resultados["metadatas"][0]):
        fragmentos.append({
            "documento": meta["documento"],
            "chunk_id": meta["chunk_id"],
            "texto": doc[:200]
        })
        contexto += f"\n---\nFuente: {meta['documento']}\n{doc}\n"

    # 2. Construir prompt y llamar a Groq
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Contexto normativo:\n{contexto}\n\nPregunta: {request.pregunta}"}
    ]

    respuesta_groq = cliente_groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.1,
        max_tokens=1024
    )

    respuesta_texto = respuesta_groq.choices[0].message.content
    duracion = int((time.time() - inicio) * 1000)
    logger.info(f"Respuesta generada ({len(respuesta_texto)} chars, {duracion}ms)")
    log_consulta(request.pregunta, respuesta_texto, fragmentos, duracion)

    return RespuestaResponse(
        respuesta=respuesta_texto,
        fragmentos_usados=fragmentos
    )

import os
import sys
from pathlib import Path
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb

# --- Configuración ---
PDFS_DIR = Path("data/pdfs")
VECTORDB_DIR = Path("data/vectordb")
COLLECTION_NAME = "normativa_ict"
CHUNK_SIZE = 500        # palabras por fragmento
CHUNK_OVERLAP = 50      # palabras de solapamiento entre fragmentos
EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"

def extraer_texto_pdf(pdf_path: Path) -> str:
    """Extrae todo el texto de un PDF."""
    reader = PdfReader(pdf_path)
    texto = ""
    for pagina in reader.pages:
        texto += pagina.extract_text() or ""
    return texto

def trocear_texto(texto: str, nombre_doc: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Divide el texto en fragmentos solapados con metadatos."""
    palabras = texto.split()
    fragmentos = []
    i = 0
    chunk_id = 0
    while i < len(palabras):
        chunk_palabras = palabras[i:i + chunk_size]
        chunk_texto = " ".join(chunk_palabras)
        fragmentos.append({
            "id": f"{nombre_doc}_chunk_{chunk_id}",
            "texto": chunk_texto,
            "metadata": {
                "documento": nombre_doc,
                "chunk_id": chunk_id,
                "palabras": len(chunk_palabras)
            }
        })
        chunk_id += 1
        i += chunk_size - overlap
    return fragmentos

def ingestar_pdfs():
    """Proceso principal de ingesta."""
    print(f"Cargando modelo de embeddings: {EMBEDDING_MODEL}")
    modelo = SentenceTransformer(EMBEDDING_MODEL)
    print("Modelo cargado.")

    print(f"Conectando a ChromaDB en: {VECTORDB_DIR}")
    cliente = chromadb.PersistentClient(path=str(VECTORDB_DIR))
    coleccion = cliente.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"Colección '{COLLECTION_NAME}' lista.")

    pdfs = list(PDFS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No se encontraron PDFs en {PDFS_DIR}")
        sys.exit(1)

    for pdf_path in pdfs:
        nombre_doc = pdf_path.stem
        print(f"\nProcesando: {pdf_path.name}")

        texto = extraer_texto_pdf(pdf_path)
        print(f"  Texto extraído: {len(texto.split())} palabras")

        fragmentos = trocear_texto(texto, nombre_doc)
        print(f"  Fragmentos generados: {len(fragmentos)}")

        ids = [f["id"] for f in fragmentos]
        textos = [f["texto"] for f in fragmentos]
        metadatas = [f["metadata"] for f in fragmentos]

        print(f"  Generando embeddings...")
        embeddings = modelo.encode(textos, show_progress_bar=True).tolist()

        print(f"  Guardando en ChromaDB...")
        coleccion.upsert(
            ids=ids,
            documents=textos,
            embeddings=embeddings,
            metadatas=metadatas
        )
        print(f"  ✓ {len(fragmentos)} fragmentos guardados.")

    total = coleccion.count()
    print(f"\nIngesta completada. Total de fragmentos en BD: {total}")

if __name__ == "__main__":
    ingestar_pdfs()

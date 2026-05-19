from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb

VECTORDB_DIR = Path("data/vectordb")
COLLECTION_NAME = "normativa_ict"
EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"

def buscar(pregunta: str, n_resultados: int = 3):
    modelo = SentenceTransformer(EMBEDDING_MODEL)
    cliente = chromadb.PersistentClient(path=str(VECTORDB_DIR))
    coleccion = cliente.get_collection(COLLECTION_NAME)

    embedding = modelo.encode(pregunta).tolist()
    resultados = coleccion.query(
        query_embeddings=[embedding],
        n_results=n_resultados
    )

    print(f"\nPregunta: {pregunta}")
    print(f"{'='*60}")
    for i, (doc, meta) in enumerate(zip(
        resultados["documents"][0],
        resultados["metadatas"][0]
    )):
        print(f"\nResultado {i+1} — {meta['documento']} (chunk {meta['chunk_id']})")
        print(f"{doc[:300]}...")

if __name__ == "__main__":
    buscar("dimensiones mínimas RITU")

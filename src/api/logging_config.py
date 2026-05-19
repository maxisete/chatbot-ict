import logging
import json
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

def setup_logging():
    """Configura el logging del sistema."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
        ]
    )

def log_consulta(pregunta: str, respuesta: str, fragmentos: list, duracion_ms: int):
    """Guarda cada consulta en un fichero JSONL para análisis posterior."""
    registro = {
        "timestamp": datetime.now().isoformat(),
        "pregunta": pregunta,
        "respuesta": respuesta,
        "num_fragmentos": len(fragmentos),
        "fuentes": list(set(f["documento"] for f in fragmentos)),
        "duracion_ms": duracion_ms
    }
    with open(LOGS_DIR / "consultas.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

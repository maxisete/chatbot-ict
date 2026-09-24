---
title: Asistente ICT
emoji: 📡
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
license: mit
short_description: Asistente de normativa ICT española
---

# 📡 Asistente ICT

Asistente de consulta sobre la normativa española de **Infraestructuras Comunes de Telecomunicaciones (ICT)**, basado en recuperación aumentada por generación (RAG). Responde en lenguaje natural citando el documento y el apartado de origen.

- **Web (PWA instalable):** https://maxisete-chatbot-ict.hf.space
- **Telegram:** [@asistente_ict_bot](https://t.me/asistente_ict_bot)

> ⚠️ Las respuestas son orientativas. Para proyectos reales consulta siempre la normativa oficial.

## Qué hace

Recibe una pregunta técnica (por ejemplo, *«¿Qué nivel de señal de satélite debe haber en la toma?»*), busca los fragmentos de normativa más relevantes y genera una respuesta que:

- se basa únicamente en esos fragmentos, sin inventar datos;
- cita la fuente y el apartado;
- presenta los valores numéricos en tablas;
- avisa cuando la respuesta requiere interpretación («⚠️ Orientativo»);
- indica claramente cuándo la información no está en las fuentes.

## Fuentes y jerarquía

| Documento | Carácter | Prioridad |
|---|---|---|
| R.D. 346/2011 | Normativa oficial vinculante | 1 |
| Orden ECE/983/2019 | Normativa oficial vinculante | 1 |
| Tablas de normativa ICT (38 tablas extraídas a texto) | Valores numéricos de la normativa oficial | 1 |
| Reglamento ICT2 de Televés | Documentación técnica complementaria | 2 |

La búsqueda consulta primero la normativa oficial. El reglamento de Televés solo se añade al contexto cuando la normativa oficial no aporta información suficiente, y en ese caso la respuesta lo indica expresamente.

## Arquitectura

```
Pregunta (web o Telegram)
        │
        ▼
FastAPI ──► Embedding de la pregunta (paraphrase-multilingual-mpnet-base-v2)
        │
        ▼
ChromaDB ──► Fragmentos más relevantes (primero normativa oficial)
        │
        ▼
Groq (openai/gpt-oss-120b) ──► Respuesta con fuentes
        │
        ├──► Web: Markdown renderizado y saneado en el navegador
        └──► Telegram: HTML adaptado (las tablas se convierten en viñetas)
```

Al arrancar, el contenedor descarga los PDF de normativa, los trocea (las tablas se trocean de una en una para no mezclar valores) y genera la base vectorial. Después levanta la API, que sirve la web y recibe el webhook de Telegram.

## Tecnologías

- **Backend:** Python 3.11, FastAPI, Uvicorn
- **Búsqueda semántica:** ChromaDB y sentence-transformers (`paraphrase-multilingual-mpnet-base-v2`)
- **Modelo de lenguaje:** `openai/gpt-oss-120b` a través de la API de Groq
- **Frontend:** HTML, CSS y JavaScript sin framework; PWA con service worker
- **Renderizado seguro:** marked 18.0.14 y DOMPurify 3.4.16
- **Bot:** API de Telegram mediante webhook integrado en FastAPI
- **Despliegue:** Docker en HuggingFace Spaces

## Seguridad

El proyecto se ha desarrollado con criterios de seguridad desde el diseño:

- **Protección frente a XSS.** Las respuestas del modelo se convierten a HTML con marked y se sanean con DOMPurify antes de mostrarse. Los mensajes del usuario y la lista de fuentes se insertan como texto, nunca como HTML. En Telegram, todo el texto se escapa antes de añadir las etiquetas de formato.
- **Dependencias de terceros verificadas.** Las librerías del navegador se alojan en el propio proyecto, con la versión fijada en el nombre del archivo, y se descargaron del registro oficial de npm comprobando su huella SHA-512. La web no depende de CDN externos.
- **Sesiones aisladas.** Cada visitante de la web tiene su propio identificador aleatorio (UUID). El servidor solo acepta identificadores con ese formato y les añade un prefijo propio, lo que impide leer o alterar el historial de otra conversación (web o Telegram).
- **Token del bot fuera de URL y logs.** El bot responde dentro de la propia respuesta del webhook, así que el servidor no necesita llamar a la API de Telegram y el token no aparece en ninguna dirección ni en los registros.
- **Errores controlados.** Los fallos del servicio de IA (límite de peticiones, falta de conexión, respuesta vacía) se traducen en mensajes claros para el usuario; el detalle técnico queda solo en los logs del servidor.
- **Secretos como variables de entorno.** Las claves se configuran como secretos del Space; el archivo `.env` está excluido de Git y `.env.example` documenta qué variables hacen falta, sin valores reales.
- **Contenedor sin privilegios.** La aplicación se ejecuta con un usuario sin permisos de administrador.

## Estructura del proyecto

```
├── Dockerfile                 # Imagen del contenedor (HuggingFace Spaces)
├── start.sh                   # Arranque: ingesta de documentos y API
├── requirements.txt           # Dependencias de Python
├── .env.example               # Plantilla de variables de entorno
├── data/pdfs/
│   └── tablas_normativa_ict.txt   # Tablas de la normativa en texto (los PDF se descargan al arrancar)
└── src/
    ├── api/
    │   ├── main.py            # API, lógica RAG, endpoint web y webhook de Telegram
    │   ├── logging_config.py  # Configuración de logs
    │   └── static/            # Interfaz web (PWA), service worker y librerías
    └── ingestion/
        ├── ingest.py          # Descarga, troceado e indexado de los documentos
        ├── test_busqueda.py   # Pruebas de la búsqueda semántica
        └── test_extraccion.py # Pruebas de la extracción de texto
```

## Ejecución local con Docker

1. Copia `.env.example` como `.env` y rellena las claves.
2. Construye la imagen y arranca el contenedor:

```bash
docker build -t chatbot-ict .
docker run -p 7860:7860 --env-file .env chatbot-ict
```

3. Abre http://localhost:7860

La primera vez tarda unos minutos, porque descarga los documentos y genera la base vectorial.

## Evolución del proyecto

- **v0.1:** construcción desde cero en una máquina virtual Debian 12, con la API y el bot de Telegram como servicios del sistema.
- **v0.2:** despliegue en HuggingFace Spaces con Docker. Troceado de las tablas de una en una, que elevó la precisión en las preguntas de prueba de 2 de 5 a 5 de 5.
- **v0.3:** interfaz adaptada al móvil e instalable como PWA. El bot de Telegram pasa de consultar periódicamente a recibir los mensajes por webhook, para adaptarse a las restricciones de red de HuggingFace.
- **Septiembre de 2026:**
  - migración a `openai/gpt-oss-120b` tras la retirada del modelo anterior;
  - renderizado seguro de las respuestas;
  - service worker que siempre sirve la versión más reciente;
  - sesiones aisladas por visitante;
  - mensajes de error claros;
  - bot de Telegram con respuesta dentro del webhook y formato adaptado.

## Limitaciones conocidas

- El historial de cada conversación se guarda en memoria y se pierde cuando el servidor se reinicia.
- En el plan gratuito de HuggingFace, el Space se duerme tras un periodo sin uso; la primera consulta después tarda unos minutos.
- El plan gratuito de Groq limita el número de consultas por minuto.

## Autor

**Maxi Jiménez Alcolea**. Técnico Superior en Sistemas de Telecomunicaciones e Informáticos, especializado en ciberseguridad. [GitHub](https://github.com/maxisete)

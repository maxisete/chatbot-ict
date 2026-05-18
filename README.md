# chatbot-ict

Asistente IA conversacional especializado en normativa española de Infraestructuras Comunes de Telecomunicaciones (ICT) en el interior de edificaciones.

Permite consultar y razonar sobre el R.D. 346/2011, la Orden ECE/983/2019 y documentación técnica relacionada, citando siempre la fuente.

## Estado del proyecto

🚧 En desarrollo inicial.

## Objetivo

Proporcionar un asistente accesible para estudiantes, instaladores, proyectistas y público interesado en ICT, capaz de:

- Responder preguntas sobre la normativa vigente citando artículo y referencia.
- Explicar conceptos técnicos (RITI, RITU, PAU, BAT, etc.).
- Orientar sobre dimensionado de instalaciones (con aviso de "orientativo").
- Funcionar desde una interfaz web y desde Telegram.

## Stack técnico

| Capa | Tecnología |
|---|---|
| Backend | Python + FastAPI |
| LLM | Groq API (Llama 3.3 70B) |
| Embeddings | sentence-transformers (local) |
| Base de datos vectorial | ChromaDB |
| Procesamiento de PDFs | pypdf |
| Interfaz web | HTML + CSS + JS |
| Bot de mensajería | python-telegram-bot |

## Fuentes documentales

- BOE: Real Decreto 346/2011, de 11 de marzo (Reglamento ICT).
- BOE: Orden ECE/983/2019, de 26 de septiembre.
- Documentación técnica libre de fabricantes (Televés, etc.).

## Aviso

Las respuestas del asistente tienen carácter **orientativo**. Para proyectos reales debe consultarse la normativa oficial y a profesionales colegiados.

## Autor

Francisco Maximiano Jiménez Alcolea ([@maxisete](https://github.com/maxisete))

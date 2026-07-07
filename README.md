<div align="center">

# 🔎 RAG-Agent-TDR

**An agentic Retrieval-Augmented Generation system for Terms of Reference (TDR / TdR) documents.**

Ask natural-language questions — in French or English — and get answers grounded in a corpus of international-development and consultancy TDRs, with cited sources.

<br/>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-1C3C3C)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-DC244C)
![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-000000)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?logo=react&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

</div>

---

## ✨ Highlights

- **🧠 Agentic pipeline** — a LangGraph state machine that *reflects* on its own retrieval and **retries with a broadened query** when the context is insufficient (a real cycle, not a linear chain).
- **🌍 Multilingual** — French / English (and Arabic-aware) via IBM Granite multilingual embeddings; answers in the language of the question.
- **📚 Grounded & cited** — answers use only the retrieved context and list their source documents; the assistant refuses questions outside the corpus instead of hallucinating.
- **🎯 Document scoping** — restrict a question to a single TDR for focused, accurate answers.
- **🔢 Metadata tools** — corpus-level questions like *“how many TDRs do you have?”* are routed to a dedicated tool that reads the true count.
- **🖥️ Full-stack** — FastAPI backend + a polished React UI (semantic search, chat assistant, persistent history).
- **📄 Robust ingestion** — PDF text extraction with OCR fallback (French Tesseract + table-layout reconstruction) for scanned documents.

---

## 🏗️ Architecture

```
┌──────────────┐        ┌─────────────────────────────────────────────┐        ┌──────────────┐
│   Frontend   │        │                  Backend                     │        │    Qdrant    │
│ React + nginx│ ─────▶ │                 (FastAPI)                    │ ─────▶ │  (vectors)   │
│  :3000       │        │                                              │        │  :6333       │
└──────────────┘        │   LangGraph agentic RAG pipeline             │        └──────────────┘
                        │                                              │        ┌──────────────┐
                        │   expand → retrieve → reflect → generate     │ ─────▶ │    Ollama    │
                        │                └── retry loop ──┘            │        │ (local LLM)  │
                        └─────────────────────────────────────────────┘        │  :11434      │
```

### The agentic RAG graph

```
                       ┌──────────── retry (broaden query) ───────────┐
                       ▼                                               │
  START ─┬─▶ expand ─▶ retrieve ─▶ reflect ─┬─(sufficient)─▶ generate ─┴─▶ END
         │                                  └─(insufficient, out of retries)─▶ generate
         └─▶ count (metadata tool) ──────────────────────────────────────────▶ END
```

- **Router** — entry branch: corpus-count questions go to a metadata tool; everything else enters the RAG pipeline.
- **Expand** — reformulates the question into several search variants (synonyms + cross-lingual).
- **Retrieve** — parent–child (“small-to-big”) vector search: embeds small child chunks for precision, returns the larger parent section for context.
- **Reflect** — an LLM judges whether the retrieved context can answer the question.
- **Retry loop** — if not, loops back to `expand` with a broadened query (capped, so it can never loop forever).
- **Generate** — produces a concise, grounded answer with an auto-appended `Sources` section.

---

## 🧰 Tech stack

| Layer          | Technology |
|----------------|-----------|
| API            | FastAPI · Uvicorn |
| Orchestration  | LangGraph · LangChain |
| Vector DB      | Qdrant |
| Embeddings     | `ibm-granite/granite-embedding-97m-multilingual-r2` (384-dim) |
| LLM            | Ollama — `mistral` (default), configurable |
| Reranker*      | `BAAI/bge-reranker-v2-m3` cross-encoder (*opt-in, off by default*) |
| Ingestion      | PyMuPDF · Tesseract OCR (fra + eng) |
| Frontend       | React · Vite · react-markdown, served by nginx |

\* The reranker improves “right document, wrong chunk” accuracy but is heavy on CPU, so it ships **disabled** (`RERANK_ENABLED=False`). Enable it on a GPU / higher-RAM host.

---

## 📁 Project structure

```
backend/
  api/
    phase9_api.py      # FastAPI app: /query, /evaluate, /health
    chat_store.py      # SQLite chat-history persistence
    routes/            # search · filters · agent · chat · documents routers
  agentic/
    graph.py           # LangGraph pipeline (router, reflect-retry cycle)
    query_expander.py  # query reformulation
    retriever.py       # vector search (+ optional reranker)
    reflector.py       # context-sufficiency judge
    generator.py
  core/                # config · qdrant_client · ollama_client
  ingestion/           # phase1 extract → phase0 classify → phase2 clean → phase3 chunk → phase4 embed/index
  scripts/
    run_ingestion.py   # one-command end-to-end ingestion
  data/raw/            # source TDR PDFs (not committed)
frontend/              # React UI (search + assistant + history)
docker-compose.yml     # Qdrant + backend + frontend
```

---

## 🚀 Quick start

### Prerequisites
- **Docker Desktop**
- **[Ollama](https://ollama.com)** running on the host with a model pulled:
  ```bash
  ollama pull mistral
  ```

### 1 — Configure
```bash
cp .env.example .env      # adjust if needed
```

### 2 — Launch the stack
```bash
docker compose up -d      # starts Qdrant, backend, and frontend
```

### 3 — Verify
```bash
curl http://localhost:8000/health
# → {"status":"healthy","qdrant":true,"ollama":true,"embeddings":"ok"}
```

### 4 — Open the app
| Service | URL |
|---------|-----|
| 🖥️ Web UI | http://localhost:3000 |
| 📘 API docs (Swagger) | http://localhost:8000/docs |
| ❤️ Health | http://localhost:8000/health |

---

## 📥 Ingesting documents

Place TDR PDFs in `backend/data/raw/`, then run the full pipeline
(extract → classify → clean → chunk → embed → index) with a single command:

```bash
python -m backend.scripts.run_ingestion
```

Sample corpus: **47 TDR documents → ~5,300 indexed chunks.**

---

## 🔌 API reference

Base URL: `http://localhost:8000`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Status of Qdrant, Ollama, and embeddings |
| `POST` | `/query` | **Main RAG endpoint** — retrieve context and generate an answer |
| `POST` | `/search` | Retrieval only (chunks + scores, no generation) |
| `POST` | `/agent/query` | RAG via the modular agent router |
| `POST` | `/evaluate` | Run RAG **and** self-grade against retrieved ground truth (offline QA) |
| `GET`  | `/filters/documents` | List indexed documents + chunk counts |
| `GET`  | `/documents/{filename}` | Serve a source PDF |
| `GET/POST/DELETE` | `/conversations…` | Persistent chat history |

**Example**

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quels sont les livrables attendus?", "context_limit": 5, "document": "TDR-17-2022-1.pdf"}'
```

```json
{
  "status": "success",
  "answer": "Les livrables détaillés sont : …",
  "sources": [{ "filename": "TDR-17-2022-1.pdf", "chunk_index": 12, "score": 0.94 }],
  "retries": 0,
  "reflection": { "sufficient": true, "reason": "…" }
}
```

> **Tip:** pass `"document": "<filename>"` (or pick a document in the UI) to scope a question to one TDR — this gives the most accurate, focused answers.

---

## 💬 Example questions

The corpus is bilingual, so ask in either language.

**French**
- « Quels sont les livrables attendus d'une mission de consultance ? »
- « Quel est le mode de sélection et le barème de notation ? »
- « Quelles qualifications sont requises pour le consultant ? »
- « Combien de TDR avez-vous ? »

**English**
- "What qualifications are required for the consultant?"
- "What are the expected deliverables of the mission?"
- "How many TDRs do you have?"

> The assistant answers **only** from the indexed documents. Ask something outside the corpus (e.g. *"What is the capital of France?"*) and it will say it cannot answer from the provided context — it does not make things up.

---

## ⚙️ Configuration

Set via `.env` (see `.env.example`):

| Variable          | Default | Description |
|-------------------|---------|-------------|
| `QDRANT_HOST` / `QDRANT_PORT` | `localhost` / `6333` | Qdrant connection |
| `COLLECTION_NAME` | `tdr_documents` | Qdrant collection |
| `EMBEDDING_MODEL` | `ibm-granite/granite-embedding-97m-multilingual-r2` | Sentence-transformer model |
| `OLLAMA_URL` / `OLLAMA_MODEL` | `…:11434` / `mistral:latest` | Ollama endpoint + model |
| `RERANK_ENABLED`  | `False` | Enable the cross-encoder reranker (GPU/high-RAM recommended) |
| `DEBUG_MODE`      | `False` | Verbose logging |

---

## 🧩 Troubleshooting

- **`/health` shows `"embeddings": "fallback (non-semantic)"`** — the embedding model failed to load; retrieval is meaningless until fixed. Ensure `sentence-transformers` and a compatible `huggingface_hub` are installed (pinned in `backend/requirements.txt`).
- **`503 Ollama is unavailable`** — start Ollama (`ollama serve`) and pull the model. From Docker, the backend reaches the host via `host.docker.internal`.
- **Empty `sources` / “could not find relevant information”** — the collection is empty; run the ingestion pipeline first.
- **Gateway Time-out** — usually the reranker on an under-resourced host. Keep `RERANK_ENABLED=False` unless you have a GPU / ample RAM.

---

## 🛠️ Common commands

```bash
docker compose up -d          # start the full stack
docker compose down           # stop everything
docker compose up -d --build backend    # rebuild after backend changes
docker logs tdr_backend -f    # follow backend logs
```

---

<div align="center">
<sub>Built with FastAPI · LangGraph · Qdrant · Ollama · React</sub>
</div>

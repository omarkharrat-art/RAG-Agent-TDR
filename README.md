# RAG-Agent-TDR

An **Agentic RAG** (Retrieval-Augmented Generation) system for **Terms of Reference (TDR / TdR)** documents used in international development and consultancy missions.

Ask natural-language questions and get answers grounded in a corpus of TDR PDFs, with cited sources. Retrieval runs over a Qdrant vector database; generation runs locally through Ollama, orchestrated with LangGraph.

---

## Architecture

```
                ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
  User query ─▶ │   Frontend   │ ───▶ │   Backend    │ ───▶ │    Qdrant    │
                │ (React/nginx)│      │  (FastAPI)   │      │ (vector DB)  │
                └──────────────┘      └──────┬───────┘      └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │    Ollama    │
                                      │  (local LLM) │
                                      └──────────────┘
```

The backend runs a LangGraph pipeline: **expand query → retrieve context → generate answer**.

---

## Tech stack

| Layer      | Technology |
|------------|-----------|
| API        | FastAPI + Uvicorn |
| Orchestration | LangGraph + LangChain |
| Vector DB  | Qdrant |
| Embeddings | `ibm-granite/granite-embedding-97m-multilingual-r2` (multilingual, 384-dim) via sentence-transformers |
| LLM        | Ollama (`llama3.2` by default) |
| Ingestion  | PyMuPDF + Tesseract OCR |
| Frontend   | React, served by nginx |

---

## Project structure

```
backend/
  api/          # FastAPI app (phase9_api.py) — /query, /evaluate, /health
  agentic/      # LangGraph pipeline: query_expander, retriever, generator, graph
  core/         # config, qdrant_client, ollama_client
  ingestion/    # PDF extraction → clean → chunk → embed → index (phase0–6)
  scripts/      # ingestion runner + test scripts
  data/raw/     # source TDR PDFs (not committed)
frontend/       # React UI
scripts/        # project-level scripts
docker-compose.yml
```

---

## Prerequisites

- **Docker Desktop** (for Qdrant + backend)
- **[Ollama](https://ollama.com)** running on the host with a model pulled:
  ```bash
  ollama pull llama3.2
  ```

---

## Quick start

1. **Configure environment** — copy the template and adjust if needed:
   ```bash
   cp .env.example .env
   ```

2. **Start the stack** (Qdrant + backend):
   ```bash
   docker compose up -d
   ```

3. **Verify it's healthy:**
   ```bash
   curl http://localhost:8000/health
   ```
   You want `{"status":"healthy","qdrant":true,"ollama":true,"embeddings":"ok"}`.
   If `embeddings` says `fallback (non-semantic)`, retrieval is broken — see Troubleshooting.

4. **Explore the API** at http://localhost:8000/docs

---

## Ingesting documents

Place TDR PDFs in `backend/data/raw/`, then run the ingestion pipeline
(extract → clean → chunk → embed → index into Qdrant):

```bash
python -m backend.scripts.run_ingestion
```

---

## API

Base URL: `http://localhost:8000`

| Method | Endpoint    | Description |
|--------|-------------|-------------|
| GET    | `/`         | Liveness check |
| GET    | `/health`   | Status of Qdrant, Ollama, and embeddings |
| POST   | `/query`    | RAG: retrieve context and generate an answer |
| POST   | `/evaluate` | Same as `/query`, but also grades the answer against a ground truth (offline QA) |

**Example query:**

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quel est l objet de la mission de consultance?", "context_limit": 5, "temperature": 0.2}'
```

**Response:**

```json
{
  "status": "success",
  "query": "...",
  "answer": "...",
  "sources": [
    { "filename": "TDR-...pdf", "chunk_index": 16, "score": 0.94 }
  ]
}
```

The assistant answers **in the same language as the question** and only from the retrieved context.

---

## Example questions

The corpus is bilingual (French / English) TDR documents, so you can ask in either language.
These questions return grounded, well-cited answers against the sample corpus:

**French**

- « Quels sont les livrables attendus d'une mission de consultance ? »
- « Quelle est la durée typique d'une mission ? »
- « Quelles qualifications sont requises pour le consultant ? »
- « Quel est l'objet de la mission de consultance ? »
- « Comment les candidats sont-ils évalués et notés ? »

**English**

- "What qualifications are required for the consultant?"
- "What are the expected deliverables of the mission?"
- "How are candidates evaluated and scored?"
- "What is the scope of the consultancy mission?"

**Try it from the command line:**

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quels sont les livrables attendus?", "context_limit": 4}'
```

> **Note:** the assistant answers **only** from the indexed TDR documents. Ask it
> something outside the corpus (e.g. "What is the capital of France?") and it will
> correctly say it cannot answer from the provided context — it does not make things up.

---

## Configuration

Set via `.env` (see `.env.example`):

| Variable          | Default | Description |
|-------------------|---------|-------------|
| `QDRANT_HOST`     | `localhost` | Qdrant host |
| `QDRANT_PORT`     | `6333` | Qdrant REST port |
| `COLLECTION_NAME` | `tdr_documents` | Qdrant collection |
| `EMBEDDING_MODEL` | `ibm-granite/granite-embedding-97m-multilingual-r2` | Sentence-transformer model |
| `OLLAMA_URL`      | `http://localhost:11434/api/generate` | Ollama endpoint |
| `OLLAMA_MODEL`    | `llama3.2:latest` | LLM model |
| `DEBUG_MODE`      | `False` | Verbose logging |

---

## Troubleshooting

- **`/health` shows `"embeddings": "fallback (non-semantic)"`** — the embedding
  model failed to load, so retrieval returns meaningless results. Ensure
  `sentence-transformers` and a compatible `huggingface_hub` are installed
  (pinned in `backend/requirements.txt`).
- **`503 Ollama is unavailable`** — start Ollama (`ollama serve`) and confirm the
  model is pulled. From inside Docker the backend reaches the host via
  `host.docker.internal`.
- **Empty `sources` / "could not find relevant information"** — the Qdrant
  collection is empty; run the ingestion pipeline first.

---

## Common commands

```bash
docker compose up -d          # start
docker compose down           # stop
docker logs tdr_backend -f    # follow backend logs
```

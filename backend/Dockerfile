FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN python -m pip install --upgrade pip setuptools wheel

COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir -f https://download.pytorch.org/whl/cpu/torch_stable.html -r backend/requirements.txt

COPY backend ./backend
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "backend.api.phase9_api:app", "--host", "0.0.0.0", "--port", "8000"]

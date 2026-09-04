FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')"
ENV HF_HUB_OFFLINE=1

COPY . backend/

EXPOSE 5000

CMD ["gunicorn", "-b", "[::]:5000", "--timeout", "300", "backend.app:app"]

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . backend/

EXPOSE 5000

CMD ["gunicorn", "-b", "[::]:5000", "backend.app:app"]

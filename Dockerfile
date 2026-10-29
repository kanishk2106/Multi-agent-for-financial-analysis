FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build the demo database inside the image (same data every time)
RUN python seed_db.py && chmod +x start.sh

CMD ["./start.sh"]

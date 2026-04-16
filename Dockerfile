FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY mmwave_vis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mmwave_vis/ .

EXPOSE 5000

CMD ["python3", "app.py"]

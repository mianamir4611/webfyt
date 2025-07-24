FROM python:3.8
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
ENV PORT=5000
CMD gunicorn --bind 0.0.0.0:$PORT main:app

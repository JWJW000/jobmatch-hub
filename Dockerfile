FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

RUN mkdir -p /app/docs/out

EXPOSE 8788

CMD ["python", "-m", "jobmatch_hub", "web", "--host", "0.0.0.0", "--port", "8788"]

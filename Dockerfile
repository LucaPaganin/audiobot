FROM python:3.12-slim

ENV PYTHONFAULTHANDLER 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONHASHSEED random
ENV PYTHONDONTWRITEBYTECODE 1
ENV PIP_NO_CACHE_DIR off
ENV PIP_DISABLE_PIP_VERSION_CHECK on
ENV PIP_DEFAULT_TIMEOUT 100

# Env vars
ENV TELEGRAM_TOKEN ${TELEGRAM_TOKEN}
ENV AZURE_SPEECH_KEY ${AZURE_SPEECH_KEY}
ENV AZURE_SPEECH_REGION ${AZURE_SPEECH_REGION}
ENV GOOGLE_API_KEY ${GOOGLE_API_KEY}
ENV GOOGLE_GEMINI_MODEL ${GOOGLE_GEMINI_MODEL}
ENV TRANSCRIPTION_ENGINE ${TRANSCRIPTION_ENGINE}
ENV TELEGRAM_BOT_TOKEN ${TELEGRAM_BOT_TOKEN}

RUN apt-get update
RUN apt-get install -y \
    python3 python3-pip \
    ffmpeg

RUN mkdir -p /codebase /storage
WORKDIR /codebase

COPY requirements.txt /codebase/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt
COPY *.py /codebase/

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80", "--reload"]

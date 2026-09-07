FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /collector

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY collector.py ./collector.py
COPY data ./data

RUN useradd --create-home --uid 10001 collector \
    && chown -R collector:collector /collector
USER collector

CMD ["python", "collector.py"]

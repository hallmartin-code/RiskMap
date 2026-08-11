# Web deployment image (Railway, Fly, Render, any container host).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Dependencies first so application edits do not invalidate the layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: legacy .ppt conversion. Adds ~500 MB to the image - uncomment only
# if you need to accept binary PowerPoint files.
# RUN apt-get update && apt-get install -y --no-install-recommends \
#         libreoffice-impress \
#     && rm -rf /var/lib/apt/lists/*

# Optional: OCR for image-only decks. Also uncomment pytesseract in requirements.txt.
# RUN apt-get update && apt-get install -y --no-install-recommends \
#         tesseract-ocr \
#     && rm -rf /var/lib/apt/lists/*

COPY pitchdeck_onepager/ ./pitchdeck_onepager/
COPY templates/ ./templates/
COPY streamlit_app.py cli.py ./
COPY .streamlit/ ./.streamlit/

RUN mkdir -p input output temp && \
    useradd --create-home --uid 10001 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Railway (and most hosts) inject PORT; 8501 is the local default.
ENV PORT=8501
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8501\")}/_stcore/health').read()"

# Shell form so $PORT is expanded at runtime. `python -m` avoids depending on
# the console script being on PATH.
CMD python -m streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0

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

# Docker does not update HOME when USER changes, so it would stay /root - which
# appuser cannot write. Streamlit creates ~/.streamlit on start and dies on the
# resulting PermissionError before it ever binds a port.
ENV HOME=/home/appuser

# Railway (and most hosts) inject PORT; 8501 is the local default.
ENV PORT=8501
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8501\")}/_stcore/health').read()"

# Shell form so $PORT is expanded at runtime; `exec` hands PID 1 to Streamlit so
# it receives SIGTERM directly (this is what the JSON-args build warning is
# really about). `python -m` avoids depending on the console script being on
# PATH. Bind `::` rather than 0.0.0.0: Railway's internal network - which the
# healthcheck uses - is IPv6-only, and 0.0.0.0 binds IPv4 only. On Linux a `::`
# socket accepts IPv4 too, so this serves both stacks.
CMD exec python -m streamlit run streamlit_app.py --server.port=${PORT:-8501} --server.address=::

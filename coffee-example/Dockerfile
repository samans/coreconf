# CORECONF coffee-maker fleet example — self-contained image.
#
# Build:  docker build -t coffee-coreconf .
# Run:    docker run --rm -p 8080:8080 coffee-coreconf
# Open:   http://localhost:8080
#
# The container runs the web console, which in turn launches the CoAP
# fleet datastore (server.py) as a subprocess on udp/5683 *inside* the
# container. Only the HTTP UI port (8080) needs to be published.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    WEBUI_HOST=0.0.0.0 \
    WEBUI_PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8080
CMD ["python", "webui/web_console.py"]

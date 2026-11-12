FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY music ./music
COPY backend ./backend
COPY pipelines ./pipelines
COPY frontend ./frontend
RUN pip install --no-cache-dir '.[stream]'
RUN useradd --create-home app && mkdir -p /app/data /app/artifacts && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

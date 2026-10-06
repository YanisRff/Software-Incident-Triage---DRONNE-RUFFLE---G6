FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
COPY scenarios ./scenarios
COPY ui ./ui
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
USER app
ENV DB_PATH=/data/analyses.db SCENARIO_ID=g06 LLM_PROVIDER=mock
EXPOSE 8000 8501
CMD ["python", "-m", "uvicorn", "ticket_app.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

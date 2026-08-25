FROM python:3.12-slim

WORKDIR /app

# Copy project metadata first for layer caching
COPY pyproject.toml ./
COPY lagent/ ./lagent/
COPY models/ ./models/
COPY profiles/ ./profiles/
COPY tests/ ./tests/

# Structural seed directories excluded from source control must exist for tests
RUN mkdir -p recordings data

# Install cross-platform runtime deps + test runner; skip dxcam/mss/pynput/pywin32
RUN pip install --no-cache-dir \
        "pydantic>=2.11.0,<3.0.0" \
        "PyYAML>=6.0.1,<7.0.0" \
        "pyzmq>=26.0.0,<27.0.0" \
        "easyocr>=1.7.0,<2.0.0" \
        "structlog>=24.0.0,<25.0.0" \
        "pytest>=7.4.0" \
    && pip install --no-cache-dir --no-deps -e .

CMD ["python", "-m", "pytest", "tests/", "-v"]

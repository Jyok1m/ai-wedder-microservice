FROM python:3.11-slim

# Crée un utilisateur non-root
RUN adduser --disabled-password --gecos '' appuser
WORKDIR /app
USER appuser

# Préinstaller uniquement pip et wheel
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copier uniquement ce qui est nécessaire
COPY app /app/app
COPY utils /app/utils
COPY README.md /app/README.md

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
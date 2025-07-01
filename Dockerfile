# Dockerfile
FROM python:3.11-slim

# Crée un utilisateur non-root
RUN adduser --disabled-password --gecos '' appuser
WORKDIR /app
USER appuser

# Copie et installation des dépendances
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# Copie du code de l'app
COPY app /app/app
COPY utils /app/utils
COPY README.md /app/README.md

# Expose le port
EXPOSE 8000

# Commande de démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
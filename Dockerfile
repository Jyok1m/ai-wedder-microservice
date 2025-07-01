FROM python:3.11-slim

# Crée un utilisateur non-root sécurisé
ENV USER=appuser
RUN useradd -ms /bin/bash $USER

WORKDIR /app

# Installer pip et wheel, puis les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copier l'application
COPY app /app/app
COPY README.md .

# Donner les droits à l'utilisateur non-root
RUN chown -R $USER:$USER /app
USER $USER

# Port attendu par Northflank
EXPOSE 8080

# Lancement FastAPI : "app.main:app" (car le fichier est /app/app/main.py)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
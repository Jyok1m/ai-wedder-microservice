FROM python:3.11-slim

# Crée un utilisateur non-root sécurisé
ENV USER=appuser
RUN useradd -ms /bin/bash $USER

WORKDIR /app

# Installer pip et wheel, puis les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copier uniquement les dossiers/fichiers utiles
COPY app /app/app
COPY utils /app/utils
COPY README.md .

# Donner les bons droits
RUN chown -R $USER:$USER /app
USER $USER

# Port attendu par Northflank
EXPOSE 8080

# Lancement FastAPI (prod-ready)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
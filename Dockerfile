# Using miniconda image for package management
FROM continuumio/miniconda3

# Environment copy
COPY environment.yml /tmp/environment.yml

# Création de l’environnement conda
RUN conda env create -f /tmp/environment.yml

# Activation par défaut de l’environnement
SHELL ["conda", "run", "-n", "ai-wedder", "/bin/bash", "-c"]

# Copie du code de l’app
WORKDIR /app

COPY . /app
COPY .env /app/.env

# Lancement de l’API
CMD ["conda", "run", "-n", "ai-wedder", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
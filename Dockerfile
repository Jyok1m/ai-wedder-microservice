# Using miniconda image for package management
FROM continuumio/miniconda3

COPY environment.yml /tmp/environment.yml
RUN conda env create -n ai-wedder -f /tmp/environment.yml

# Activation par défaut de l’environnement
SHELL ["conda", "run", "-n", "ai-wedder", "/bin/bash", "-c"]

# Copie du code de l’app
WORKDIR /app

COPY app /app/app
COPY utils /app/utils
COPY README.md /app/README.md

# Lancement de l’API
CMD ["conda", "run", "-n", "ai-wedder", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

EXPOSE 8000
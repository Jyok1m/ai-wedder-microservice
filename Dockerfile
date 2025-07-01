FROM continuumio/miniconda3

# Copier et créer l’environnement
COPY environment.yml /tmp/environment.yml
RUN conda env create -n ai-wedder -f /tmp/environment.yml

# Définir le répertoire de travail
WORKDIR /app

# Copier uniquement les fichiers utiles
COPY app /app/app
COPY utils /app/utils
COPY README.md /app/README.md

# Exposer le port HTTP utilisé
EXPOSE 8000

# CMD qui garde uvicorn vivant
CMD ["conda", "run", "--no-capture-output", "-n", "ai-wedder", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
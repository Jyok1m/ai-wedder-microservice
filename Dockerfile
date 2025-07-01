FROM continuumio/miniconda3

# Copier l'environnement et le créer
COPY environment.yml /tmp/environment.yml
RUN conda env create -n ai-wedder -f /tmp/environment.yml

# Préparation de l'activation automatique de l'env conda
RUN echo "conda activate ai-wedder" >> ~/.bashrc

# Définir le répertoire de travail
WORKDIR /app

# Copier uniquement les fichiers nécessaires
COPY app /app/app
COPY utils /app/utils
COPY README.md /app/README.md

# Exposer le port de l’API
EXPOSE 8000

# Commande de démarrage via un shell interactif
CMD ["bash", "-c", "source activate ai-wedder && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
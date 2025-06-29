import pandas as pd
import os
import ast
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.db.mongo import db
from transformers import pipeline
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

router = APIRouter()
load_dotenv()

# Chargement une fois au démarrage
classifier = pipeline(
    "text-classification",
    model="Jyokim/camembert-wedder-nps-classifier",
    tokenizer="Jyokim/camembert-wedder-nps-classifier",
)

clusterer = pipeline(
    task="zero-shot-classification",
    model="cmarkea/distilcamembert-base-nli",
    tokenizer="cmarkea/distilcamembert-base-nli"
)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def gpt_model(prompt, model="gpt-3.5-turbo"): 
    try:
        messages = [{"role": "user", "content": prompt}]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ GPT API error: {e}")
        return ""

def get_clustering_prompt(reviews_as_str):
    return f"""Tu es un expert en traiteurs de mariage. \
    Voici des avis de clients sur des traiteurs de mariage :\n{reviews_as_str}\n \
    Propose-moi la liste la plus pertinente des 10 catégories thématiques pour classer ou regrouper des avis de clients sur des traiteurs de mariage. \
    Renvoie uniquement une liste de mots ou expressions, sous forme de liste Python. Exemple : ["nourriture", "service", "ambiance", "ponctualité", "prix", "professionnalisme", "présentation"] etc. \
    Ne donne pas d'explications, juste la liste. \
    """

def get_reviews_for_clustering_prompt(review_samples):
    reviews_for_clustering_prompt = ""
    for i, row in review_samples.iterrows():
        reviews_for_clustering_prompt += f"[Avis {i+1}]: {row['text']}\n"
    return reviews_for_clustering_prompt

def get_ai_clusters(labels, scores):
    aiClusters = []
    for label, score in zip(labels, scores):
        aiClusters.append({"label": label, "score": score})
    return aiClusters

def get_catering_with_reviews(db_model):
    return list(db_model.aggregate([
        {
            "$group": {
                "_id": "$venue",
                "reviews": {
                    "$push": {
                        "text": "$text",
                        "aiClusters": "$aiClusters"
                    }
                }
            }
        },
        {
            "$lookup": {
                "from": "venues",
                "localField": "_id",
                "foreignField": "_id",
                "as": "venue_data"
            }
        },
        {
            "$project": {
                "_id": 0,
                "cateringCompanyId": {"$first": "$venue_data._id"},
                "cateringCompanyName": {"$first": "$venue_data.name"},
                "reviews": 1
            }
        }
    ]))

def batch_reviews(reviews, batch_size=10):
    for i in range(0, len(reviews), batch_size):
        yield reviews[i:i + batch_size]

@router.post("/summarize")
def updateReviews():
    def event_stream():
        reviews = list(db["reviews"].find({}, {"_id": 1, "text": 1}))
        yield f"🔍 {len(reviews)} reviews trouvés\n"

        # ------------------------------------------------------------------ #
        #           Étape 1 : Classification et Clustering des avis          #
        # ------------------------------------------------------------------ #
        
        # We retrieve a sample of reviews to clusterize them
        df_sample = pd.DataFrame(reviews).sample(n=150, random_state=42).reset_index(drop=True) # Sample for clustering
        reviews_for_clustering_prompt = get_reviews_for_clustering_prompt(df_sample)
        clustering_prompt = get_clustering_prompt(reviews_for_clustering_prompt)

        suggested_labels = []

        raw_labels = gpt_model(clustering_prompt)

        if not raw_labels:
            yield "❌ Aucune réponse obtenue depuis l'API OpenAI. Vérifie ta clé API, ta connexion ou ton quota.\n"
            return

        try:
            suggested_labels = ast.literal_eval(raw_labels)
            assert isinstance(suggested_labels, list)
        except Exception as e:
            yield f"❌ Erreur lors de l’analyse de la réponse : {e}\nRéponse GPT brute :\n{raw_labels}\n"
            return

        if not suggested_labels:
            yield "❌ Aucune étiquette valide n’a été extraite. Abandon...\n"
            return
        else:
            yield f"✅ Labels de clustering récupérés : {suggested_labels}\n"

        for idx, review in enumerate(reviews):
            text = review.get("text", "")

            if not text:
                continue

            # ------------------------- Classification ------------------------- #
            
            """
            The first step is to classify each review with a sentiment analysis model.
            Here, we use the classifier I built with Camembert. 
            I have trained it and push it on Hugging Face so that it can be used in production.
            The classifier is a simple text classification model that predicts the sentiment of each review.
            It is a French model that predicts the sentiment of the review as either "positive", "negative" or "neutral".
            """

            sentiment = classifier(text)[0]

            # --------------------------- Clustering --------------------------- #

            """
            The second step is to clusterize the reviews based on their content.
            For this step, I will use 2 techniques : 
                1. The first technique is about getting 10 labels based on the overall review tendency.
                2. The second technique is about using DistilCamembert Zero-Shot to clusterize the reviews based on the labels obtained in the first step.
            I am basically inducing the labels from the reviews themselves, so that they are more relevant to the dataset and to my specific needs.
            """

            clusterer_result = clusterer(sequences=text, candidate_labels=suggested_labels, hypothesis_template="Cet avis concerne {}.")
            ai_clusters = get_ai_clusters(labels=clusterer_result["labels"], scores=clusterer_result["scores"])

            # --------------------------- Update DB --------------------------- #

            """
            I update the review in the database with the sentiment and the clusters.
            """

            db["reviews"].update_one(
                {"_id": review["_id"]},
                {"$set": {
                    "aiSentiment": sentiment["label"],
                    "aiConfidenceScore": sentiment["score"],
                    "aiClusters": ai_clusters
                }}
            )

            yield f"[{idx+1}/{len(reviews)}] Sentiment + clusters enregistrés\n"
            time.sleep(0.1) # Ici on met une pause pour ne pas surcharger l'API
        
        yield "Résumés globaux par traiteur...\n"

        # ------------------------------------------------------------------ #
        #                         Step 2 : Summarize                         #
        # ------------------------------------------------------------------ #

        """
        In this step, I will summarize the reviews for each catering company.
        I will use the OpenAI GPT model to summarize the reviews.
        The summary will be stored in the database for each catering company.
        I will also use the reviews to generate a global score for each catering company.
        """

        catering_with_reviews = get_catering_with_reviews(db["reviews"])

        for _, entry in enumerate(tqdm(catering_with_reviews, desc="Processing catering companies")):
            name = entry["cateringCompanyName"]
            reviews = entry["reviews"]

            summaries = []

            # Batch processing of reviews to avoid hitting token limits
            for batch in batch_reviews(reviews):
                batch_text = ""

                for r in batch:
                    review_ai_clusters = ", ".join([c["label"] for c in r.get("aiClusters", [])])
                    if r.get("text"):
                        batch_text += f"\n\n [AVIS] {r['text']} [CLUSTERS] {review_ai_clusters}"

                batch_prompt = f"""
                Tu es un assistant d'analyse d'avis pour des traiteurs de mariage.

                Voici un extrait d'avis avec les thèmes principaux de chaque avis pour le traiteur **{name}** :

                {batch_text}

                Résume les points importants en quelques phrases.
                """
                try:
                    summaries.append(gpt_model(batch_prompt))
                except Exception as e:
                    yield f"Erreur GPT batch pour {name}: {e}"
                    continue

            full_summary = "\n\n".join(summaries)

            final_prompt = f"""
            Tu es un assistant d'analyse d'avis pour des traiteurs de mariage.

            Voici les résumés intermédiaires des avis pour le traiteur **{name}** :

            {full_summary}

            Ta tâche :
            1. Fais un résumé synthétique global des avis.
            2. Analyse et synthétise les points majeurs évoqués (forces, faiblesses, répétitions...).
            3. Attribue un score global subjectif sur 100 basé sur la qualité perçue.

            ⚠️ Le format de sortie **doit être exactement** celui-ci :

            Résumé : [texte ici]

            Points clés : [texte ici]

            Score global : [nombre entre 0 et 100]%

            Exemple valide :
            Résumé : Ce traiteur est connu pour sa qualité de service et la présentation des plats. Si vous souhaitez un repas raffiné, c'est le traiteur idéal. Cependant, certains ont trouvé les prix un peu élevés par rapport à d'autres traiteurs...
            Points clés : Les invités ont particulièrement apprécié la qualité du service et la présentation des plats...
            Score global : 88%
            """
            
            try:
                result = gpt_model(final_prompt)
                if "Résumé :" in result and "Points clés :" in result and "Score global :" in result:
                    parts = result.split("Score global :")
                    if len(parts) == 2:
                        core, score = parts
                        summary, key_points = core.split("Points clés :", 1)
                        summary = summary.replace("Résumé :", "", 1).strip() if "Résumé :" in summary else summary.strip()
                        db["venues"].update_one(
                            {"_id": entry["cateringCompanyId"]},
                            {
                                "$set": {
                                    "aiSummary": summary.strip(),
                                    "aiKeyPoints": key_points.strip(),
                                    "aiGlobalScore": score.strip()
                                }
                            }
                        )
                        yield f"Résumé pour {name} enregistré\n"
                else:
                    yield f"Résultat inattendu pour {name} : {result}\n"
            except Exception as e:
                yield f"Aïe ! Erreur GPT pour {name} : {e}\n"
                continue
        
        yield "Traitement terminé.\n"

    return StreamingResponse(event_stream(), media_type="text/plain")
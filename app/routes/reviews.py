import pandas as pd
import os
import ast

from fastapi import APIRouter
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

# OpenAI management

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def gpt_model(prompt, model="gpt-3.5-turbo"): 
  messages = [{"role": "user", "content": prompt}]
  response = client.chat.completions.create(
      model=model,
      messages=messages,
      temperature=0.3,
  )
  return response.choices[0].message.content

@router.post("/summarize")
def updateReviews():
    reviews = list(db["reviews"].find({}, {"_id": 1, "text": 1}))

    # ------------------------------------------------------------------ #
    #                          Step 1 : Classify                         #
    # ------------------------------------------------------------------ #

    for review in reviews:
        text = review.get("text", "")
        if not text:
            continue

        sentiment = classifier(text)[0]

        db["reviews"].update_one(
            {"_id": review["_id"]},
            {"$set": {
                "aiSentiment": sentiment["label"],
                "aiConfidenceScore": sentiment["score"]
            }}
        )

    print(f"Classification completed for {len(reviews)} reviews.")

    # ------------------------------------------------------------------ #
    #                         Step 2 : Clusterize                        #
    # ------------------------------------------------------------------ #

    df_sample = pd.DataFrame(reviews).sample(n=200, random_state=42).reset_index(drop=True)

    sample_reviews = ""
    
    for i, row in df_sample.iterrows():
        sample_reviews += f"Avis {i+1}: {row['text']}\n\n"

    prompt = f"""Tu es un expert en clustering d'avis de traiteurs de mariage. \
    Voici des avis de clients sur des traiteurs pour des mariages :\n\n{sample_reviews}\n\n \
    Ta tâche est de proposer une liste de 10 catégories thématiques pour classer ou regrouperdes avis de clients sur des traiteurs pour des mariages. \
    Donne uniquement une liste de mots ou expressions, sous forme de liste Python. Exemple : ["nourriture", "service", "ambiance", "ponctualité", "prix", "professionnalisme", "présentation"] etc. \
    Ne donne pas d'explications, juste la liste. \
    """

    suggested_labels = ast.literal_eval(gpt_model(prompt))

    # DistilCamembert Zero-Shot
    clustered_reviews = []
    for review in reviews:
        text = review.get("text", "")
        if text:
            clusterer_result = clusterer(
                sequences=text,
                candidate_labels=suggested_labels,
                hypothesis_template="Cet avis concerne {}.",
            )

            aiClusters = []

            for label, score in zip(clusterer_result["labels"], clusterer_result["scores"]):
                aiClusters.append({"label": label, "score": score})

            clustered_reviews.append({"review_id": review["_id"], "text": text, "aiClusters": aiClusters})

    for review in clustered_reviews:
        db["reviews"].update_one(
            {"_id": review["review_id"]},
            {"$set": {"aiClusters": review["aiClusters"]}},
        )
    
    print(f"Clustering completed for {len(clustered_reviews)} reviews.")

    # ------------------------------------------------------------------ #
    #                         Step 3 : Summarize                         #
    # ------------------------------------------------------------------ #

    # Regroupe les reviews par traiteur
    catering_reviews = list(db["reviews"].aggregate([
        {
            "$group": {
                "_id": "$venue",
                "reviews": {
                    "$push": {
                        "text": "$text"
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

    for entry in tqdm(catering_reviews):
        name = entry["cateringCompanyName"]
        reviews = entry["reviews"]

        summaries = []

        for batch in batch_reviews(reviews):
            batch_text = "\n\n".join([r["text"] for r in batch if r.get("text")])
            batch_prompt = f"""
            Tu es un assistant d'analyse d'avis pour des traiteurs de mariage.

            Voici un extrait d'avis pour le traiteur **{name}** :

            {batch_text}

            Résume les points importants en quelques phrases.
            """
            try:
                summaries.append(gpt_model(batch_prompt))
            except Exception as e:
                print(f"Erreur GPT batch pour {name}: {e}")
                continue

        full_summary = "\n\n".join(summaries)

        final_prompt = f"""
        Tu es un assistant d'analyse d'avis pour des traiteurs de mariage.

        Voici les résumés intermédiaires des avis pour le traiteur **{name}** :

        {full_summary}

        1. Fais un résumé synthétique global des avis.
        2. Détaille les points majeurs évoqués (forces, faiblesses, répétitions...).
        3. Attribue un score global subjectif sur 100 basé sur la qualité perçue.

        Donne la réponse structurée comme ceci :
        Résumé : ...
        Points clés : ...
        Score global : ...
        """
        try:
            result = gpt_model(final_prompt)
            if "Résumé :" in result and "Points clés :" in result and "Score global :" in result:
                parts = result.split("Score global :")
                if len(parts) == 2:
                    core, score = parts
                    summary, key_points = core.split("Points clés :", 1)
                    db["venues"].update_one(
                        {"_id": entry["cateringCompanyId"]},
                        {
                            "$set": {
                                "aiSummary": summary.replace("Résumé :", "").strip(),
                                "aiKeyPoints": key_points.strip(),
                                "aiGlobalScore": score.strip()
                            }
                        }
                    )
            else:
                print(f"⚠️ Résultat inattendu pour {name}: {result}")
        except Exception as e:
            print(f"Erreur GPT finale pour {name}: {e}")
            continue

    print("Résumé global terminé.")

    return {"message": "Classification terminée"}
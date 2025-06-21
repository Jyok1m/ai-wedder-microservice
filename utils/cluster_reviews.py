import os
from dotenv import load_dotenv
from pymongo import MongoClient
from transformers import pipeline

SUGGESTED_LABELS = ["qualité des plats", "service client", "professionnalisme de l'équipe", "présentation des plats", "flexibilité", "rapport qualité/prix", "communication", "adaptabilité", "satisfaction des invités", "expérience globale"]

def connect_to_db():
  load_dotenv()
  MONGODB_URI = os.getenv("MONGODB_URI")
  client = MongoClient(MONGODB_URI)
  
  if client is not None:
    print("Connected to DB")
    return client
  else:
    print("Failed to connect to DB")
    return None

def get_reviews_from_db(client):
  if client is None:
      return []

  db = client["ai-wedder"]
  Review = db["reviews"]
  
  reviews = Review.find({}, {"_id": 1, "text": 1})
  
  if not reviews:
      print("No reviews found in the database.")
  
  return list(reviews)

def cluster_reviews(reviews, clusterer):  
  clustered_reviews = []
  for review in reviews:
      text = review.get("text", "")
      if text:
          clusterer_result = clusterer(sequences=text, candidate_labels=SUGGESTED_LABELS, hypothesis_template="Cet avis concerne {}.")
          aiClusters = []
          
          for label, score in zip(clusterer_result["labels"], clusterer_result["scores"]):
            aiClusters.append({ "label": label, "score": score })
          
          clustered_reviews.append({
            "review_id": review["_id"],
            "text": text,
            "aiClusters": aiClusters
          })
          
          print(f"Clustered review {review['_id']} with clusters: {aiClusters}")
  
  return clustered_reviews

def save_to_db(client, clustered_reviews):
  if client is None:
      return
  
  db = client["ai-wedder"]
  Review = db["reviews"]
  
  for review in clustered_reviews:
      Review.update_one(
          {"_id": review["review_id"]},
          {"$set": {"aiClusters": review["aiClusters"]}},
      )
      print(f"Updated review {review['review_id']} with clusters {review["aiClusters"]} in the database.")

# Usage
if __name__ == "__main__":
    client = connect_to_db()
    reviews = get_reviews_from_db(client)
    clusterer = pipeline(
        task="zero-shot-classification",
        model="cmarkea/distilcamembert-base-nli",
        tokenizer="cmarkea/distilcamembert-base-nli"
    )
    clustered_reviews = cluster_reviews(reviews, clusterer)
    save_to_db(client, clustered_reviews)

    # Print done message and classified reviews
    print("Clustering complete !")
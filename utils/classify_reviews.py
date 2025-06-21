import os
from dotenv import load_dotenv
from pymongo import MongoClient
from transformers import pipeline

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

def classify_reviews(reviews):
  # todo : place outside
  classifier = pipeline("text-classification", model="Jyokim/camembert-wedder-nps-classifier", tokenizer="Jyokim/camembert-wedder-nps-classifier")
  
  classified_reviews = []
  for review in reviews:
      text = review.get("text", "")
      if text:
          sentiment = classifier(text)
          classified_reviews.append({
              "review_id": review["_id"],
              "text": text,
              "aiSentiment": sentiment[0]["label"],
              "aiConfidenceScore": sentiment[0]["score"]
          })
          
          print(f"Classified review {review['_id']} with sentiment {sentiment[0]['label']} and score {sentiment[0]['score']}")
  
  return classified_reviews

def save_to_db(client, classified_reviews):
  if client is None:
      return
  
  db = client["ai-wedder"]
  Review = db["reviews"]
  
  for classified_review in classified_reviews:
      Review.update_one(
          {"_id": classified_review["review_id"]},
          {"$set": {"aiSentiment": classified_review["aiSentiment"],
                    "aiConfidenceScore": classified_review["aiConfidenceScore"]}
          },
      )
      print(f"Updated review {classified_review['review_id']} with sentiment {classified_review['aiSentiment']} and score {classified_review['aiConfidenceScore']}")

# Usage
if __name__ == "__main__":
    client = connect_to_db()
    reviews = get_reviews_from_db(client)
    classified_reviews = classify_reviews(reviews)
    save_to_db(client, classified_reviews)

    # Print done message and classified reviews
    print("Classification complete !")
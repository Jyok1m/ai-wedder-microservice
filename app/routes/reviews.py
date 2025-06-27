from fastapi import APIRouter
from app.db.mongo import db
from transformers import pipeline

router = APIRouter()

# Chargement une fois au démarrage
classifier = pipeline(
    "text-classification",
    model="Jyokim/camembert-wedder-nps-classifier",
    tokenizer="Jyokim/camembert-wedder-nps-classifier",
)

@router.get("/classify")
def get_classified_reviews():
    reviews = list(db["reviews"].find({}, {"_id": 1, "text": 1}))

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

    return {"message": "Classification terminée"}
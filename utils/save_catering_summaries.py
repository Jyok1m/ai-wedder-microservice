import os
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId


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


def load_summaries_from_file(path="microservice/data/catering_reviews_summary.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"✅ Loaded {len(data)} summaries from {path}")
        return data
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return []


def save_summaries_to_db(client, summaries):
    if client is None:
        return

    db = client["ai-wedder"]
    Venue = db["venues"]

    for entry in summaries:
        venue_id = ObjectId(entry.get("cateringCompanyId"))
        summary = entry.get("summary", "").strip()
        key_points = entry.get("key_points", "").strip()
        global_score = entry.get("global_score", "").strip()

        if not venue_id:
            print("⚠️ Skipping: no venue ID")
            continue

        update_result = Venue.update_one(
            {"_id": venue_id},
            {
                "$set": {
                    "aiSummary": summary,
                    "aiKeyPoints": key_points,
                    "aiGlobalScore": global_score,
                }
            },
        )

        if update_result.modified_count > 0:
            print(f"✅ Updated venue {venue_id}")
        else:
            print(f"⚠️ No update for venue {venue_id}")


if __name__ == "__main__":
    client = connect_to_db()
    summaries = load_summaries_from_file()
    save_summaries_to_db(client, summaries)
    print("🎉 Upload completed")

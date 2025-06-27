from bson import ObjectId

def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    if "venue" in doc and isinstance(doc["venue"], ObjectId):
        doc["venue"] = str(doc["venue"])
    return doc
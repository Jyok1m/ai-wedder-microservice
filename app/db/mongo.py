from pymongo import MongoClient
from app.config import MONGODB_URI, DATABASE

client = MongoClient(MONGODB_URI)
db = client[DATABASE]

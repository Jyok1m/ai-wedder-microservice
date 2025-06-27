# Entry point
from fastapi import FastAPI
from app.routes import reviews

app = FastAPI()
app.include_router(reviews.router, prefix="/reviews")
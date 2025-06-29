# Entry point
from fastapi import FastAPI
from app.routes import reviews, hello

app = FastAPI()
app.include_router(reviews.router, prefix="/reviews")
app.include_router(hello.router, prefix="/hello")
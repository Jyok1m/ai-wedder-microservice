from fastapi import APIRouter

router = APIRouter()

@router.get("")
def say_hello():
    return {"message": "Hello, World as GET!"}

@router.post("")
def say_hello():
    return {"message": "Hello, World as POST!"}

@router.put("")
def say_hello():
    return {"message": "Hello, World as PUT!"}

@router.delete("")
def say_hello():
    return {"message": "Hello, World as DELETE!"}
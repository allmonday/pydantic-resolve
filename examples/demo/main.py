from typing import Optional, List
from fastapi import FastAPI, Depends, Query
from pydantic import BaseModel
from pydantic_resolve import Resolver

app = FastAPI(debug=True)

class Person(BaseModel):
    name: str
    age: int
    

class Book(BaseModel):
    title: str
    year: int
    author: Optional[Person] = None
    
    async def resolve_author(self):
        return get_author(self.title)


@app.get("/books", response_model=list[Book])
async def books():
    books = fetch_books()
    resolver = Resolver()
    results = await resolver.resolve(books)
    return results
    

def fetch_books() -> list[Book]:
    return [Book(**book) for book in books]

def get_author(book_name: str) -> Person:
    author = book_author_mapping[book_name]
    return Person(**[person for person in persons if person['name'] == author][0])


books = [
    {"title": "1984", "year": 1949},
    {"title": "To Kill a Mockingbird", "year": 1960},
    {"title": "The Great Gatsby", "year": 1925}
]
persons = [
    {"name": "George Orwell", "age": 46},
    {"name": "Harper Lee", "age": 89},
    {"name": "F. Scott Fitzgerald", "age": 44}
]
book_author_mapping = {
    "1984": "George Orwell",
    "To Kill a Mockingbird": "Harper Lee",
    "The Great Gatsby": "F. Scott Fitzgerald"
}

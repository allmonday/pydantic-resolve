from aiodataloader import DataLoader
from pydantic import BaseModel

BOOKS = {
    1: [{'name': 'book1'}, {'name': 'book2'}],
    2: [{'name': 'book3'}, {'name': 'book4'}],
    3: [{'name': 'book1'}, {'name': 'book2'}],
}

class Book(BaseModel):
    name: str
    public: str = 'public'

class BookLoader(DataLoader):
    async def batch_load_fn(self, keys):
        books = [[Book(**bb) for bb in BOOKS.get(k, [])] for k in keys]
        return books
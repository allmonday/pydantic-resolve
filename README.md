
## install

```shell
pip install pydantic-resolve
```

## demo

```python
from pydantic_resolve import resolver

class Book(BaseModel):
    name: str

class Student(BaseModel):
    name: str
    intro: str = ''
    def resolve_intro(self):
        return f'hello {self.name}'
    
    books: tuple[Book, ...] = tuple()
    async def resolve_books(self):
        return await get_books()

async def get_books():
    await asyncio.sleep(1)
    return [Book(name="sky"), Book(name="sea")]

class TestResolver(unittest.IsolatedAsyncioTestCase):

    async def test_resolver_1(self):
        stu = Student(name="boy")
        result = await resolver(stu)
        expected = {
            'name': 'boy',
            'intro': 'hello boy',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        self.assertEqual(result.dict(), expected)

    async def test_resolver_2(self):
        stu = [Student(name="boy")]
        result = await resolver(stu)
        expected = {
            'name': 'boy',
            'intro': 'hello boy',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        self.assertEqual(result[0].dict(), expected)

    async def test_schema(self):
        # Student.update_forward_refs(Book=Book)
        schema = Student.schema_json()
        expected = '''{"title": "Student", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}, "intro": {"title": "Intro", "default": "", "type": "string"}, "books": {"title": "Books", "default": [], "type": "array", "items": {"$ref": "#/definitions/Book"}}}, "required": ["name"], "definitions": {"Book": {"title": "Book", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}}, "required": ["name"]}}}'''
        self.assertEqual(schema, expected)
```

### TODO:
play with aiodataloader

## unittest

```shell
poetry run python -m unittest
```

## coverage 

```shell
poetry run coverage run -m pytest
poetry run coverage report -m
```

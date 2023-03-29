import unittest
from pydantic import BaseModel
from typing import Optional
from pydantic_resolve import resolve


class DetailA(BaseModel):
    name: str = ''

class ServiceDetail1(BaseModel):
    detail_a: Optional[DetailA] = None

    def resolve_detail_a(self):
        return DetailA(name='hello world')

    detail_b: str = ''

    def resolve_detail_b(self):
        return 'good'

class Service(BaseModel):
    service_detail_1: Optional[ServiceDetail1] = None
    def resolve_service_detail_1(self):
        return ServiceDetail1()

    service_detail_2: str = ''
    def resolve_service_detail_2(self):
        return "detail_2"


class TestObjectResolver(unittest.IsolatedAsyncioTestCase):

    async def test_resolver_1(self):
        s = Service()
        result = await resolve(s)
        expected = {
            "service_detail_1": {
                "detail_a": {
                    "name": "hello world"
                },
                "detail_b": "good"
            },
            "service_detail_2": "detail_2" 
        }
        self.assertEqual(result.dict(), expected)
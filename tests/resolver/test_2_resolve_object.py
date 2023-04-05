import pytest
from pydantic import BaseModel
from typing import Optional
from pydantic_resolve import Resolver
import asyncio
import time

class DetailA(BaseModel):
    name: str = ''

class ServiceDetail1(BaseModel):
    detail_a: Optional[DetailA] = None

    async def resolve_detail_a(self):
        await asyncio.sleep(1)
        return DetailA(name='hello world')

    detail_b: str = ''

    async def resolve_detail_b(self):
        await asyncio.sleep(1)
        return 'good'

class Service(BaseModel):
    service_detail_1: Optional[ServiceDetail1] = None
    async def resolve_service_detail_1(self):
        await asyncio.sleep(1)
        return ServiceDetail1()

    service_detail_1b: Optional[ServiceDetail1] = None
    async def resolve_service_detail_1b(self):
        await asyncio.sleep(1)
        return ServiceDetail1()

    service_detail_2: str = ''
    async def resolve_service_detail_2(self):
        await asyncio.sleep(1)
        return "detail_2"

    service_detail_3: str = ''
    async def resolve_service_detail_3(self):
        await asyncio.sleep(1)
        return "detail_3"

    service_detail_4: str = ''
    async def resolve_service_detail_4(self):
        await asyncio.sleep(1)
        return "detail_4"

@pytest.mark.asyncio
async def test_resolve_object():
    t = time.time()
    s = Service()
    result = await Resolver().resolve(s)
    expected = {
        "service_detail_1": {
            "detail_a": {
                "name": "hello world"
            },
            "detail_b": "good"
        },
        "service_detail_1b": {
            "detail_a": {
                "name": "hello world"
            },
            "detail_b": "good"
        },
        "service_detail_2": "detail_2",
        "service_detail_3": "detail_3",
        "service_detail_4": "detail_4",
    }
    assert result.dict() == expected
    delta = time.time() - t

    assert delta < 2.1
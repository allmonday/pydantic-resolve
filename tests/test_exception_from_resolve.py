import asyncio
import unittest
from pydantic import BaseModel
from pydantic_resolve import resolve
import pytest

class CustomException(Exception):
    pass

class CustomException2(Exception):
    pass

class TestResolverException(unittest.IsolatedAsyncioTestCase):

    async def test_exception_1(self):
        class Service(BaseModel):
            service_detail: str = ''
            async def resolve_service_detail(self):
                raise CustomException2('oops')

            service_detail_2: str = ''
            async def resolve_service_detail_2(self):
                raise CustomException('oops')

        s = Service()
        with pytest.raises((CustomException, CustomException2), match="oops") as e:
            await resolve(s)
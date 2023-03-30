import unittest
from pydantic import BaseModel
from pydantic_resolve import resolve, ResolverTargetAttrNotFound
import pytest

class TestResolverException(unittest.IsolatedAsyncioTestCase):

    async def test_exception_1(self):
        class Service(BaseModel):
            service_detail: str = ''
            def resolve_service_details(self):
                return "detail"

        s = Service()
        with pytest.raises(ResolverTargetAttrNotFound, match="attribute service_details not found"):
            await resolve(s)

    async def test_exception_2(self):
        class Service(BaseModel):
            service_detail: str = ''
            def resolve_service(self):
                return "detail"

        s = Service()
        with pytest.raises(ResolverTargetAttrNotFound, match="attribute service not found"):
            await resolve(s)
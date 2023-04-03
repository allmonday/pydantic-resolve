import unittest
from pydantic import BaseModel
from pydantic_resolve import resolve, ResolverTargetAttrNotFound
import pytest
from pydantic import ValidationError

class TestResolverException(unittest.IsolatedAsyncioTestCase):

    async def test_exception_1(self):
        class Service(BaseModel):

            service_detail: int = 0
            def resolve_service_detail(self):
                return 'abc'

            class Config:
                validate_assignment = True  # <<< required.

        s = Service()
        with pytest.raises(ValidationError):
            await resolve(s)

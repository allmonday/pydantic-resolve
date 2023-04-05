from __future__ import annotations
from pydantic_resolve import ResolverTargetAttrNotFound, resolve
from pydantic import BaseModel, ValidationError
import pytest

class Service(BaseModel):
    service_detail: str = ''
    def resolve_service_details(self):
        return "detail"

@pytest.mark.asyncio
async def test_exception_1():
    with pytest.raises(ResolverTargetAttrNotFound, match="attribute service_details not found"):
        s = Service()
        await resolve(s)

class CustomException(Exception):
    pass

class CustomException2(Exception):
    pass

class Service2(BaseModel):
    service_detail: str = ''
    async def resolve_service_detail(self):
        raise CustomException2('oops')

    service_detail_2: str = ''
    async def resolve_service_detail_2(self):
        raise CustomException('oops')

@pytest.mark.asyncio
async def test_custom_exception():
    with pytest.raises((CustomException, CustomException2), match="oops"):
        s = Service2()
        await resolve(s)


class Service3(BaseModel):
    service_detail: int = 0
    def resolve_service_detail(self):
        return 'abc'  # wrong type

    class Config:
        validate_assignment = True  # <<< required.

@pytest.mark.asyncio
async def test_pydantic_validate_exception():
    with pytest.raises(ValidationError):
        s = Service3()
        await resolve(s)

class Service4(BaseModel):
    service_detail: int = 0
    def resolve_service_detail(self):
        raise AttributeError('test')

@pytest.mark.asyncio
async def test_attribute_error():
    with pytest.raises(AttributeError):
        s = Service4()
        await resolve(s)

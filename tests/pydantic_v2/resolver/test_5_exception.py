from __future__ import annotations
from pydantic_resolve import ResolverTargetAttrNotFound, Resolver
from pydantic import ConfigDict, BaseModel, ValidationError
import pytest

class Service(BaseModel):
    service_detail: str = ''
    def resolve_service_details(self) -> str:
        return "detail"

@pytest.mark.asyncio
async def test_exception_1():
    with pytest.raises(ResolverTargetAttrNotFound, match="attribute service_details not found"):
        s = Service()
        await Resolver().resolve(s)

class CustomException(Exception):
    pass

class CustomException2(Exception):
    pass

class Service2(BaseModel):
    service_detail: str = ''
    async def resolve_service_detail(self) -> str:
        raise CustomException2('oops')

    service_detail_2: str = ''
    async def resolve_service_detail_2(self) -> str:
        raise CustomException('oops')

@pytest.mark.asyncio
async def test_custom_exception():
    with pytest.raises((CustomException, CustomException2), match="oops"):
        s = Service2()
        await Resolver().resolve(s)


class Service3(BaseModel):
    service_detail: int = 0
    def resolve_service_detail(self) -> int: 
        return 'abc'  # type:ignore
    model_config = ConfigDict(validate_assignment=True)

@pytest.mark.asyncio
async def test_pydantic_validate_exception():
    with pytest.raises(ValidationError):
        s = Service3()
        await Resolver().resolve(s)

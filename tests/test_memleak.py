from uuid import uuid1, UUID
from pydantic_resolve import Resolver
import gc
from pydantic import BaseModel, ConfigDict
import psutil
import pytest


class SchemaA(BaseModel):
    id: str
    int_field: int
    binary_field: UUID
    float_field: float
    
    model_config = ConfigDict(from_attributes=True)


def str_uuid1():
    return str(uuid1())

@pytest.mark.asyncio
async def test_mem_leak_2():
    process = psutil.Process()
    gc.collect()

    memory_start = process.memory_info().rss
    for _ in range(50000):
        await Resolver().resolve(SchemaA(
            id=str_uuid1(),
            int_field=123,
            binary_field=uuid1(),
            float_field=123.456
        ))

    memory_after_del = process.memory_info().rss
    diff = memory_after_del - memory_start
    print(memory_after_del, memory_start, diff/1024)
    assert diff/1024 < 500  # less than 500KB increase
"""Tests for GraphQL datetime and other special type support."""
import json
from datetime import datetime, date, time
from decimal import Decimal
from uuid import uuid4
from typing import List, Optional, Annotated

import pytest
from pydantic import BaseModel, PlainSerializer

from pydantic_resolve import base_entity, query, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

BaseEntity = base_entity()


# Custom UtcDatetime type (simulates user-defined type with custom serializer)
# Using when_used="always" to ensure it's always applied
def serialize_datetime_to_z(dt: datetime | None) -> str | None:
    """Serialize datetime to ISO 8601 format with 'Z' suffix (UTC)."""
    if dt is None:
        return None
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


UtcDatetime = Annotated[
    datetime,
    PlainSerializer(serialize_datetime_to_z, return_type=str, when_used="always")
]


class DateTimeEntity(BaseModel, BaseEntity):
    __relationships__ = []
    id: int
    name: str
    created_at: datetime
    birth_date: Optional[date] = None
    schedule_time: Optional[time] = None
    price: Optional[Decimal] = None
    uuid_field: Optional[str] = None
    # Custom UtcDatetime type
    utc_time: Optional[UtcDatetime] = None

    @query
    async def get_all(cls) -> List['DateTimeEntity']:
        return [
            DateTimeEntity(
                id=1,
                name="Event 1",
                created_at=datetime(2024, 1, 1, 12, 30, 45),
                birth_date=date(2024, 1, 1),
                schedule_time=time(14, 30, 0),
                price=Decimal("99.99"),
                uuid_field=str(uuid4()),
                utc_time=datetime(2024, 1, 1, 12, 30, 45),
            ),
        ]


class TestDateTimeJSONSerialization:
    """Test datetime and special type JSON serialization."""

    def setup_method(self):
        """Set up test environment."""
        self.er_diagram = BaseEntity.get_diagram()
        config_global_resolver(self.er_diagram)
        self.handler = GraphQLHandler(self.er_diagram)

    @pytest.mark.asyncio
    async def test_datetime_json_serialization(self):
        """Verify datetime types can be JSON serialized."""
        result = await self.handler.execute(
            "{ dateTimeEntityGetAll { id name created_at birth_date schedule_time price utc_time } }"
        )

        # Critical test: result must be JSON serializable
        json_str = json.dumps(result)
        assert "created_at" in json_str
        # Verify datetime is serialized as ISO string
        assert "2024-01-01T12:30:45" in json_str

    @pytest.mark.asyncio
    async def test_custom_plain_serializer(self):
        """Verify PlainSerializer is triggered correctly with mode='json'."""
        result = await self.handler.execute(
            "{ dateTimeEntityGetAll { id utc_time } }"
        )

        # Verify custom serializer is triggered (with Z suffix)
        utc_time = result["data"]["dateTimeEntityGetAll"][0]["utc_time"]
        assert utc_time.endswith("Z"), f"Expected Z suffix, got: {utc_time}"

    @pytest.mark.asyncio
    async def test_date_serialization(self):
        """Verify date type is serialized as ISO string."""
        result = await self.handler.execute(
            "{ dateTimeEntityGetAll { id birth_date } }"
        )

        json_str = json.dumps(result)
        assert "2024-01-01" in json_str

    @pytest.mark.asyncio
    async def test_time_serialization(self):
        """Verify time type is serialized as ISO string."""
        result = await self.handler.execute(
            "{ dateTimeEntityGetAll { id schedule_time } }"
        )

        json_str = json.dumps(result)
        # time should be serialized as ISO format
        assert "14:30:00" in json_str

    @pytest.mark.asyncio
    async def test_decimal_serialization(self):
        """Verify Decimal type is serialized as string/number."""
        result = await self.handler.execute(
            "{ dateTimeEntityGetAll { id price } }"
        )

        json_str = json.dumps(result)
        assert "99.99" in json_str


class TestDateTimeSDLGeneration:
    """Test datetime SDL generation."""

    def setup_method(self):
        """Set up test environment."""
        self.er_diagram = BaseEntity.get_diagram()
        config_global_resolver(self.er_diagram)

    def test_datetime_field_in_schema(self):
        """Test that datetime fields have correct type in schema."""
        schema_builder = SchemaBuilder(self.er_diagram)
        sdl = schema_builder.build_schema()

        # DateTime should be mapped to String (GraphQL scalar)
        assert "created_at: DateTime!" in sdl or "created_at: String!" in sdl

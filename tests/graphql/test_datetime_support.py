"""Tests for GraphQL datetime and other special type support."""
import json
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID, uuid4
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
    uuid_field: Optional[UUID] = None
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
                uuid_field=uuid4(),
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
            "{ DateTimeEntity { get_all { id name created_at birth_date schedule_time price utc_time } } }"
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
            "{ DateTimeEntity { get_all { id utc_time } } }"
        )

        # Verify custom serializer is triggered (with Z suffix)
        utc_time = result["data"]["DateTimeEntity"]["get_all"][0]["utc_time"]
        assert utc_time.endswith("Z"), f"Expected Z suffix, got: {utc_time}"

    @pytest.mark.asyncio
    async def test_date_serialization(self):
        """Verify date type is serialized as ISO string."""
        result = await self.handler.execute(
            "{ DateTimeEntity { get_all { id birth_date } } }"
        )

        json_str = json.dumps(result)
        assert "2024-01-01" in json_str

    @pytest.mark.asyncio
    async def test_time_serialization(self):
        """Verify time type is serialized as ISO string."""
        result = await self.handler.execute(
            "{ DateTimeEntity { get_all { id schedule_time } } }"
        )

        json_str = json.dumps(result)
        # time should be serialized as ISO format
        assert "14:30:00" in json_str

    @pytest.mark.asyncio
    async def test_decimal_serialization(self):
        """Verify Decimal type is serialized as string/number."""
        result = await self.handler.execute(
            "{ DateTimeEntity { get_all { id price } } }"
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
        """Temporal/UUID fields render as real GraphQL scalars, not String."""
        schema_builder = SchemaBuilder(self.er_diagram)
        sdl = schema_builder.build_schema()

        # Required scalar -> NonNull; Optional scalar -> nullable (no `!`).
        assert "created_at: DateTime!" in sdl
        assert "birth_date: Date" in sdl      # Optional[date] -> nullable Date
        assert "schedule_time: Time" in sdl
        assert "uuid_field: UUID" in sdl
        # None of these should fall back to String.
        assert "created_at: String" not in sdl
        assert "uuid_field: String" not in sdl

    def test_scalars_advertised_in_introspection(self):
        """__schema must advertise UUID/DateTime/Date/Time as scalar types."""
        handler = GraphQLHandler(self.er_diagram)
        schema = handler.introspection._generator.generate()
        scalar_names = {
            t["name"] for t in schema["types"] if t.get("kind") == "SCALAR"
        }
        assert {"UUID", "DateTime", "Date", "Time"}.issubset(scalar_names)


# Separate diagram so the arg-conversion entity doesn't widen the SDL tests above.
ArgBase = base_entity()
_ARG_RECEIVED: dict = {}


class ArgEntity(BaseModel, ArgBase):
    """Exercises scalar arg coercion (single, list[T], Optional[list[T]])."""
    __relationships__ = []
    id: int

    @query
    async def by_ids(cls, ids: List[UUID]) -> List["ArgEntity"]:
        _ARG_RECEIVED["ids"] = [type(x).__name__ for x in ids]
        return []

    @query
    async def by_whens(cls, whens: List[datetime]) -> List["ArgEntity"]:
        _ARG_RECEIVED["whens"] = [type(x).__name__ for x in whens]
        return []

    @query
    async def by_single(cls, u: UUID, d: date, t: time) -> List["ArgEntity"]:
        _ARG_RECEIVED["single"] = (type(u).__name__, type(d).__name__, type(t).__name__)
        return []


class TestScalarArgConversion:
    """Methods must receive real UUID/datetime/date/time objects, not strings."""

    def setup_method(self):
        self.er_diagram = ArgBase.get_diagram()
        config_global_resolver(self.er_diagram)
        self.handler = GraphQLHandler(self.er_diagram)

    @pytest.mark.asyncio
    async def test_list_uuid_arg(self):
        await self.handler.execute(
            '{ ArgEntity { by_ids(ids: ["550e8400-e29b-41d4-a716-446655440000"]) { id } } }'
        )
        assert _ARG_RECEIVED["ids"] == ["UUID"]

    @pytest.mark.asyncio
    async def test_list_datetime_arg(self):
        await self.handler.execute(
            '{ ArgEntity { by_whens(whens: ["2024-01-01T10:00:00"]) { id } } }'
        )
        assert _ARG_RECEIVED["whens"] == ["datetime"]

    @pytest.mark.asyncio
    async def test_single_scalar_args(self):
        await self.handler.execute(
            '{ ArgEntity { by_single(u: "550e8400-e29b-41d4-a716-446655440000", d: "2024-03-04", t: "11:22:33") { id } } }'
        )
        assert _ARG_RECEIVED["single"] == ("UUID", "date", "time")

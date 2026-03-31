import pytest
from pydantic import BaseModel, ValidationError

from pydantic_resolve.utils.er_diagram import (
	Entity,
	ErDiagram,
	Relationship,
)


class A(BaseModel):
	fk: int


class T1(BaseModel):
	id: int


class T2(BaseModel):
	id: int


def dummy_loader(*args, **kwargs):
	return None


def test_relationship_single_target_no_field_name_required():
	cfg = Entity(
		kls=A,
		relationships=[
			Relationship(fk="fk", name="t1", target=T1, loader=dummy_loader),
		],
	)
	assert isinstance(cfg, Entity)


def test_relationship_none_default_conflict_raises():
	with pytest.raises(ValidationError):
		Relationship(
			fk="fk",
			name="t1",
			target=T1,
			loader=dummy_loader,
			fk_none_default=None,
			fk_none_default_factory=list,
		)


def test_entity_duplicate_field_name_raises():
	"""Test that duplicate field_name in relationships raises ValidationError."""
	with pytest.raises(ValidationError):
		Entity(
			kls=A,
			relationships=[
				Relationship(fk="fk", name="t1", target=T1, loader=dummy_loader),
				Relationship(fk="fk", name="t1", target=T1, loader=dummy_loader),
			],
		)


def test_entity_distinct_field_names_allowed():
	"""Test that different field_names for the same field are allowed."""
	entity = Entity(
		kls=A,
		relationships=[
			Relationship(fk="fk", name="t1", target=T1, loader=dummy_loader),
			Relationship(fk="fk", name="t1_alt", target=T1, loader=dummy_loader),
		],
	)
	assert isinstance(entity, Entity)

def test_entity_allows_distinct_targets_per_field():
	entity = Entity(
		kls=A,
		relationships=[
			Relationship(fk="fk", name="t1", target=T1, loader=dummy_loader),
			Relationship(fk="fk", name="t2", target=T2, loader=dummy_loader),
		],
	)
	assert isinstance(entity, Entity)


def test_erdiagram_duplicate_entity_kls_raises():
	cfg = Entity(
		kls=A,
		relationships=[Relationship(fk="fk", name="t1", target=T1, loader=dummy_loader)],
	)
	with pytest.raises(ValidationError):
		ErDiagram(configs=[cfg, cfg])
import pytest
from pydantic import BaseModel, ValidationError

from pydantic_resolve.utils.er_diagram import (
	Entity,
	ErDiagram,
	Link,
	MultipleRelationship,
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


def test_relationship_single_target_no_biz_required():
	cfg = Entity(
		kls=A,
		relationships=[
			Relationship(field="fk", target_kls=T1, loader=dummy_loader),
		],
	)
	assert isinstance(cfg, Entity)


def test_relationship_none_default_conflict_raises():
	with pytest.raises(ValidationError):
		Relationship(
			field="fk",
			target_kls=T1,
			loader=dummy_loader,
			field_none_default=None,
			field_none_default_factory=list,
		)


def test_entity_duplicate_field_target_raises():
	with pytest.raises(ValidationError):
		Entity(
			kls=A,
			relationships=[
				Relationship(field="fk", target_kls=T1, loader=dummy_loader),
				Relationship(field="fk", target_kls=T1, loader=dummy_loader),
			],
		)


def test_entity_duplicate_multiple_relationship_raises():
	with pytest.raises(ValidationError):
		Entity(
			kls=A,
			relationships=[
				MultipleRelationship(
					field="fk",
					target_kls=list[T1],
					links=[Link(biz="a", loader=dummy_loader)],
				),
				MultipleRelationship(
					field="fk",
					target_kls=list[T1],
					links=[Link(biz="b", loader=dummy_loader)],
				),
			],
		)

def test_multiple_relationship_unique_links_allowed():
	entity = Entity(
		kls=A,
		relationships=[
			MultipleRelationship(
				field="fk",
				target_kls=list[T1],
				links=[
					Link(biz="a", loader=dummy_loader),
					Link(biz="b", loader=dummy_loader),
				],
			)
		],
	)
	assert isinstance(entity, Entity)

def test_multiple_relationship_duplicated_disallowed():
	with pytest.raises(ValidationError):
		Entity(
			kls=A,
			relationships=[
				MultipleRelationship(
					field="fk",
					target_kls=list[T1],
					links=[
						Link(biz="a", loader=dummy_loader),
						Link(biz="a", loader=dummy_loader),
					],
				)
			],
		)

def test_entity_allows_distinct_targets_per_field():
	entity = Entity(
		kls=A,
		relationships=[
			Relationship(field="fk", target_kls=T1, loader=dummy_loader),
			Relationship(field="fk", target_kls=T2, loader=dummy_loader),
		],
	)
	assert isinstance(entity, Entity)


def test_erdiagram_duplicate_entity_kls_raises():
	cfg = Entity(
		kls=A,
		relationships=[Relationship(field="fk", target_kls=T1, loader=dummy_loader)],
	)
	with pytest.raises(ValidationError):
		ErDiagram(configs=[cfg, cfg])
import pytest
from pydantic import BaseModel
from pydantic import ValidationError
from pydantic_resolve.utils.er_diagram import Entity, Relationship, ErDiagram


class A(BaseModel):
	fk: int


class T1(BaseModel):
	id: int


class T2(BaseModel):
	id: int


def dummy_loader(*args, **kwargs):
	return None


def test_valid_single_target_no_biz_required():
	# Single target_kls for a field doesn't require biz
	cfg = Entity(
		kls=A,
		relationships=[
			Relationship(field="fk", target_kls=T1, loader=dummy_loader),
		],
	)
	assert isinstance(cfg, Entity)


def test_duplicate_triple_raises():
	with pytest.raises(ValueError):
		Entity(
			kls=A,
			relationships=[
				Relationship(field="fk", biz="x", target_kls=T1, loader=dummy_loader),
				Relationship(field="fk", biz="x", target_kls=T1, loader=dummy_loader),
			],
		)


def test_multiple_targets_require_non_empty_unique_biz_empty_or_duplicate():
	# duplicate biz under same field but different target_kls is ok
	Entity(
		kls=A,
		relationships=[
			Relationship(field="fk", biz="x", target_kls=T1, loader=dummy_loader),
			Relationship(field="fk", biz="x", target_kls=T2, loader=dummy_loader),
		],
	)


def test_multiple_targets_with_unique_biz_is_ok():
	cfg = Entity(
		kls=A,
		relationships=[
			Relationship(field="fk", biz="alpha", target_kls=T1, loader=dummy_loader),
			Relationship(field="fk", biz="beta", target_kls=T2, loader=dummy_loader),
		],
	)
	assert isinstance(cfg, Entity)


def test_multiple_targets_with_unique_target_kls_is_ok():
	cfg = Entity(
		kls=A,
		relationships=[
			Relationship(field="fk", target_kls=T1, loader=dummy_loader),
			Relationship(field="fk", target_kls=T2, loader=dummy_loader),
		],
	)
	assert isinstance(cfg, Entity)


def test_erdiagram_valid_distinct_kls():
	cfg1 = Entity(kls=A, relationships=[Relationship(field="fk", target_kls=T1, loader=dummy_loader)])
	cfg2 = Entity(kls=T1, relationships=[])  # using T1 as a model with no relationships
	diagram = ErDiagram(configs=[cfg1, cfg2])
	assert isinstance(diagram, ErDiagram)


def test_erdiagram_duplicate_kls_raises():
	cfg1 = Entity(kls=A, relationships=[Relationship(field="fk", target_kls=T1, loader=dummy_loader)])
	cfg2 = Entity(kls=A, relationships=[])  # duplicate kls
	with pytest.raises(ValueError):
		ErDiagram(configs=[cfg1, cfg2])


def test_multiple_targets_biz_none_or_non_empty():
	# duplicate biz under same field should fail
	with pytest.raises(ValidationError):
		Entity(
			kls=A,
			relationships=[
				Relationship(field="fk", biz="", target_kls=T2, loader=dummy_loader),
			],
		)
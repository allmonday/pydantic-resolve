import pytest
from pydantic import BaseModel

from pydantic_resolve.utils.er_diagram import ErConfig, Relationship, ErDiagram


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
	cfg = ErConfig(
		kls=A,
		relationships=[
			Relationship(field="fk", target_kls=T1, loader=dummy_loader),
		],
	)
	assert isinstance(cfg, ErConfig)


def test_duplicate_triple_raises():
	with pytest.raises(ValueError):
		ErConfig(
			kls=A,
			relationships=[
				Relationship(field="fk", biz="x", target_kls=T1, loader=dummy_loader),
				# duplicate of (field, biz, target_kls)
				Relationship(field="fk", biz="x", target_kls=T1, loader=dummy_loader),
			],
		)


def test_multiple_targets_require_non_empty_unique_biz_missing():
	# two distinct target_kls under same field, but no biz provided -> error
	with pytest.raises(ValueError):
		ErConfig(
			kls=A,
			relationships=[
				Relationship(field="fk", target_kls=T1, loader=dummy_loader),
				Relationship(field="fk", target_kls=T2, loader=dummy_loader),
			],
		)


def test_multiple_targets_require_non_empty_unique_biz_empty_or_duplicate():
	# empty biz should fail
	with pytest.raises(ValueError):
		ErConfig(
			kls=A,
			relationships=[
				Relationship(field="fk", biz="", target_kls=T1, loader=dummy_loader),
				Relationship(field="fk", biz="x", target_kls=T2, loader=dummy_loader),
			],
		)

	# duplicate biz under same field should fail
	with pytest.raises(ValueError):
		ErConfig(
			kls=A,
			relationships=[
				Relationship(field="fk", biz="x", target_kls=T1, loader=dummy_loader),
				Relationship(field="fk", biz="x", target_kls=T2, loader=dummy_loader),
			],
		)


def test_multiple_targets_with_unique_biz_is_ok():
	cfg = ErConfig(
		kls=A,
		relationships=[
			Relationship(field="fk", biz="alpha", target_kls=T1, loader=dummy_loader),
			Relationship(field="fk", biz="beta", target_kls=T2, loader=dummy_loader),
		],
	)
	assert isinstance(cfg, ErConfig)


def test_erdiagram_valid_distinct_kls():
	cfg1 = ErConfig(kls=A, relationships=[Relationship(field="fk", target_kls=T1, loader=dummy_loader)])
	cfg2 = ErConfig(kls=T1, relationships=[])  # using T1 as a model with no relationships
	diagram = ErDiagram(configs=[cfg1, cfg2])
	assert isinstance(diagram, ErDiagram)


def test_erdiagram_duplicate_kls_raises():
	cfg1 = ErConfig(kls=A, relationships=[Relationship(field="fk", target_kls=T1, loader=dummy_loader)])
	cfg2 = ErConfig(kls=A, relationships=[])  # duplicate kls
	with pytest.raises(ValueError):
		ErDiagram(configs=[cfg1, cfg2])


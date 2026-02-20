import pytest
from pydantic import BaseModel
from pydantic_resolve.analysis import Analytic
from pydantic_resolve.exceptions import ResolverTargetAttrNotFound, MissingCollector
from typing import Optional, List


# ============ Test 1: Empty class ============
class EmptyClass(BaseModel):
    """Only basic fields, no resolve/post"""
    id: int
    name: str


def test_empty_class():
    """Empty class should have no resolve/post, should_traverse=False"""
    result = Analytic().scan(EmptyClass)
    prefix = 'tests.analysis.test_analysis_edge_cases'

    assert result[f'{prefix}.EmptyClass']['resolve'] == []
    assert result[f'{prefix}.EmptyClass']['post'] == []
    assert result[f'{prefix}.EmptyClass']['should_traverse'] is False


# ============ Test 2: Missing field ============
class MissingField(BaseModel):
    name: str
    # Field does not exist, but resolve method is defined
    def resolve_user(self):
        pass


def test_resolve_missing_field():
    """Should raise exception when resolve method has no corresponding field"""
    with pytest.raises(ResolverTargetAttrNotFound):
        Analytic().scan(MissingField)


class MissingPostField(BaseModel):
    name: str
    # Field does not exist, but post method is defined
    def post_total(self):
        return 0


def test_post_missing_field():
    """Should raise exception when post method has no corresponding field"""
    with pytest.raises(ResolverTargetAttrNotFound):
        Analytic().scan(MissingPostField)


# ============ Test 3: Collector not declared ============
# Scenario: Child sends data to name_collector, but Parent does not declare this collector
class ChildForCollector(BaseModel):
    name: str
    # Declare to send name to name_collector
    __pydantic_resolve_collect__ = {'name': 'name_collector'}


class ParentWithCollector(BaseModel):
    child: ChildForCollector

    # Declared different_collector, but not name_collector
    related_names: List[str] = []

    def post_related_names(self, collector=None):
        # Use different_collector instead of name_collector
        return []


# Define collector parameter outside the class
ParentWithCollector.__pydantic_resolve_collect__ = {'related_names': 'different_collector'}


def test_collector_not_declared():
    """Should raise exception when collector is not declared in ancestor nodes"""
    # Analyzer should detect that child sends to name_collector, but parent does not declare it
    with pytest.raises(MissingCollector):
        Analytic().scan(ParentWithCollector)


# ============ Test 4: Expose conflict ============
# Two fields in the same class expose the same alias
class UserExpose(BaseModel):
    id: int


class ExposeConflictModel(BaseModel):
    name: str
    title: str
    user: Optional[UserExpose] = None

    # Two fields expose the same alias - should be class attribute
    __pydantic_resolve_expose__ = {'name': 'exposed_name', 'title': 'exposed_name'}


def test_expose_conflict():
    """Should raise exception when multiple fields expose the same alias"""
    with pytest.raises(ValueError):
        Analytic().scan(ExposeConflictModel)


# ============ Test 5: Inheritance chain ============
class BaseModelWithResolve(BaseModel):
    id: int
    name: str

    def resolve_name(self):
        return self.name


class ChildModel(BaseModel):
    value: int


class InheritedModel(BaseModel):
    base: BaseModelWithResolve
    child: ChildModel


def test_inheritance_chain():
    """Inheritance chain should correctly resolve resolve methods"""
    result = Analytic().scan(InheritedModel)
    prefix = 'tests.analysis.test_analysis_edge_cases'

    # BaseModelWithResolve has resolve_name
    assert 'resolve_name' in result[f'{prefix}.BaseModelWithResolve']['resolve']

    # InheritedModel should have object_fields containing base
    inherited = result[f'{prefix}.InheritedModel']
    assert 'base' in inherited['object_fields']
    # Note: child has no resolve/post method, will not be traversed


# ============ Test 6: Self-reference class ============
class SelfReference(BaseModel):
    """Self-reference class"""
    id: int
    name: Optional['SelfReference'] = None


def test_self_reference_class():
    """Self-reference class should be handled correctly"""
    result = Analytic().scan(SelfReference)
    prefix = 'tests.analysis.test_analysis_edge_cases'

    # Self-reference class has no resolve/post, so should_traverse=False
    assert result[f'{prefix}.SelfReference']['should_traverse'] is False


# ============ Test 7: Self-reference class with resolve ============
class SelfReferenceWithResolve(BaseModel):
    """Self-reference class with resolve method"""
    id: int
    name: Optional['SelfReference'] = None

    def resolve_name(self):
        return self.name


def test_self_reference_with_resolve():
    """Self-reference class with resolve method should be handled correctly"""
    result = Analytic().scan(SelfReferenceWithResolve)
    prefix = 'tests.analysis.test_analysis_edge_cases'

    # Self-reference class has resolve_name, should_traverse=True
    assert 'resolve_name' in result[f'{prefix}.SelfReferenceWithResolve']['resolve']
    assert result[f'{prefix}.SelfReferenceWithResolve']['should_traverse']

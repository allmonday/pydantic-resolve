from __future__ import annotations
from pydantic import BaseModel, ValidationError
from pydantic_resolve import build_object, LoaderDepend, Resolver, build_list
from typing import List, Optional
import pytest


departments = [
    dict(id=1, name='INFRA'),
    dict(id=2, name='DevOps'),
    dict(id=3, name='Sales'),
]

teams = [
    dict(id=1, department_id=1, name="K8S"),
    dict(id=2, department_id=1, name="MONITORING"),
    dict(id=3, department_id=1, name="Jenkins"), 
    dict(id=5, department_id=2, name="Frontend"),
    dict(id=6, department_id=2, name="Bff"),
    dict(id=7, department_id=2, name="Backend"), 
    dict(id=8, department_id=3, name="CAT"),
    dict(id=9, department_id=3, name="Account"),
    dict(id=10, department_id=3, name="Operation"),
]

department_lead = [
    dict(id=1, department_id=1, name='mike'),
    dict(id=2, department_id=2, name='john'),
    dict(id=3, department_id=3, name='ralf'),
]

members = [
    dict(id=1, team_id=1, name="Sophia", gender='female'),
    dict(id=2, team_id=1, name="Jackson", gender='male'),
    dict(id=3, team_id=2, name="Olivia", gender='female'),
    dict(id=4, team_id=2, name="Liam", gender='male'),
    dict(id=5, team_id=3, name="Emma", gender='female'),
    dict(id=6, team_id=4, name="Noah", gender='male'),
    dict(id=7, team_id=5, name="Ava", gender='female'),
    dict(id=8, team_id=6, name="Lucas", gender='male'),
    dict(id=9, team_id=6, name="Isabella", gender='female'),
    dict(id=10, team_id=6, name="Mason", gender='male'),
    dict(id=11, team_id=7, name="Mia", gender='female'),
    dict(id=12, team_id=8, name="Ethan", gender='male'),
    dict(id=13, team_id=8, name="Amelia", gender='female'),
    dict(id=14, team_id=9, name="Oliver", gender='male'),
    dict(id=15, team_id=9, name="Charlotte", gender='female'),
    dict(id=16, team_id=10, name="Jacob", gender='male'),
    dict(id=17, team_id=10, name="Abigail", gender='female'),
    dict(id=18, team_id=10, name="Daniel", gender='male'),
    dict(id=19, team_id=10, name="Emily", gender='female'),
    dict(id=20, team_id=10, name="Ella", gender='female')
]

class DepartmentBase(BaseModel):
    id: int
    name: str

class TeamBase(BaseModel):
    id: int
    name: str


class MemberBase(BaseModel):
    id: int
    name: str
    gender: str


async def lead_batch_load_fn(department_ids):
    return build_list(department_lead, department_ids, lambda t: t['department_id'])

async def teams_batch_load_fn(department_ids):
    return build_list(teams, department_ids, lambda t: t['department_id'])

async def members_batch_load_fn(team_ids):
    return build_list(members, team_ids, lambda t: t['team_id'])


class Result(BaseModel):
    departments: List[Department]

class Department(DepartmentBase):
    teams: List[Team] = []

    def resolve_teams(self, loader=LoaderDepend(teams_batch_load_fn)):
        return loader.load(self.id)

    lead: Optional[Lead] = None

    def resolve_lead(self, loader=LoaderDepend(lead_batch_load_fn)):
        return loader.load(self.id)

class Team(TeamBase):
    members: List[Member] = []

    def resolve_members(self, loader=LoaderDepend(members_batch_load_fn)):
        return loader.load(self.id)

class Member(MemberBase):
    ...

class Lead(BaseModel):
    id: int
    name: str


@pytest.mark.asyncio
async def test_error():
    """
    1. generate data from departments to members  (top to bottom)
    """
    Result.update_forward_refs()
    department_ids = {2, 3}
    _departments = [Department(**d) for d in departments if d['id'] in department_ids] 
    result = Result(departments=_departments)
    with pytest.raises(ValidationError):
        await Resolver().resolve(result)


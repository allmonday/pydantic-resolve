from __future__ import annotations
import json
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, build_list, mapper, ensure_subset
from readme_demo.datum import datum, DepartmentBase, TeamBase, MemberBase


async def teams_batch_load_fn(department_ids):
    return build_list(datum.teams, department_ids, lambda t: t['department_id'])

async def members_batch_load_fn(team_ids):
    return build_list(datum.members, team_ids, lambda t: t['team_id'])


class Result(BaseModel):
    departments: List[Department] = []
    def resolve_departments(self):
        return [d for d in datum.departments if d['id'] in {1,2}] 

class Department(DepartmentBase):
    teams: List[Team] = []
    def resolve_teams(self, loader=LoaderDepend(teams_batch_load_fn)):
        return loader.load(self.id)

@ensure_subset(TeamBase)
class Team(BaseModel):
    id: int
    name: str

    members: List[Member] = []
    @mapper(lambda members: [Member(id=m['id'], name=m['name'], greet=f"hi, im {m['name']}") for m in members])
    def resolve_members(self, loader=LoaderDepend(members_batch_load_fn)):
        return loader.load(self.id)

class Member(BaseModel):
    id: int
    name: str
    greet: str  # greet is not compatible with input data, need map


async def main():
    """
    1. generate data from departments to members  (top to bottom)
    2. use ensure_subset to pick the necessary fields
    3. use @mapper to manually handle the mapping logic
    """
    result = Result()
    data = await Resolver(annotation_class=Result).resolve(result)
    print(json.dumps(data.dict(), indent=2))

asyncio.run(main())
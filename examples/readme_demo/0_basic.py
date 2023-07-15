from __future__ import annotations
import json
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, build_list
from readme_demo.datum import datum, DepartmentBase, TeamBase, MemberBase


async def teams_batch_load_fn(department_ids):
    return build_list(datum.teams, department_ids, lambda t: t['department_id'])

async def members_batch_load_fn(team_ids):
    return build_list(datum.members, team_ids, lambda t: t['team_id'])


class Result(BaseModel):
    departments: List[Department]

class Department(DepartmentBase):
    teams: List[Team] = []
    def resolve_teams(self, loader=LoaderDepend(teams_batch_load_fn)):
        return loader.load(self.id)

class Team(TeamBase):
    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(members_batch_load_fn)):
        return loader.load(self.id)

class Member(MemberBase):
    ...


async def main():
    """
    1. generate data from departments to members  (top to bottom)
    """
    Result.update_forward_refs()
    department_ids = {2,3}
    departments = [Department(**d) for d in datum.departments if d['id'] in department_ids] 
    result = Result(departments=departments)
    data = await Resolver(annotation_class=Result).resolve(result)
    print(json.dumps(data.dict(), indent=2))

asyncio.run(main())
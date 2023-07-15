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


class Member(MemberBase):
    ...

class Team(TeamBase):
    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(members_batch_load_fn)):
        return loader.load(self.id)


class Department(DepartmentBase):
    teams: List[Team] = []
    def resolve_teams(self, loader=LoaderDepend(teams_batch_load_fn)):
        return loader.load(self.id)


class Result(BaseModel):
    departments: List[Department] = []
    def resolve_departments(self, context):
        return [d for d in datum.departments if d['id'] in context['department_ids']] 


async def main():
    """
    1. generate data from departments to members  (top to bottom)
    2. use context to pass params, resolve_method must use `context` to read it
    """
    result = Result()
    data = await Resolver(context={
        'department_ids': {1}
    }).resolve(result)
    print(json.dumps(data.dict(), indent=2))

asyncio.run(main())
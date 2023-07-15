from __future__ import annotations
import json
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, build_list
from readme_demo.datum import datum, DepartmentBase, TeamBase, MemberBase
from aiodataloader import DataLoader

class TeamDataLoader(DataLoader):
    async def batch_load_fn(self, department_ids):
        return build_list(datum.teams, department_ids, lambda t: t['department_id'])

class MemberDataLoader(DataLoader):
    gender: str
    async def batch_load_fn(self, team_ids):
        members = [m for m in datum.members if m['gender'] == self.gender]
        return build_list(members, team_ids, lambda t: t['team_id'])


class Result(BaseModel):
    departments: List[Department]

class Department(DepartmentBase):
    teams: List[Team] = []
    def resolve_teams(self, loader=LoaderDepend(TeamDataLoader)):
        return loader.load(self.id)

class Team(TeamBase):
    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(MemberDataLoader)):
        return loader.load(self.id)

class Member(MemberBase):
    ...


async def main():
    """
    1. generate data from departments to members  (top to bottom)
    2. filter all female member. add gender field in MemberDataLoader
    """
    Result.update_forward_refs()
    department_ids = {2,3}
    departments = [Department(**d) for d in datum.departments if d['id'] in department_ids] 
    result = Result(departments=departments)
    resolver = Resolver(
        annotation_class=Result,
        loader_filters={
            MemberDataLoader: {'gender': 'female'}
        })
    data = await resolver.resolve(result)
    print(json.dumps(data.dict(), indent=2))

asyncio.run(main())
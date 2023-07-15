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
    async def batch_load_fn(self, team_ids):
        return build_list(datum.members, team_ids, lambda t: t['team_id'])


class Member(MemberBase):
    ...

class Team(TeamBase):
    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(MemberDataLoader)):
        return loader.load(self.id)

    member_count: int = 0
    def post_member_count(self):
        return len(self.members)

class Department(DepartmentBase):
    teams: List[Team] = []
    def resolve_teams(self, loader=LoaderDepend(TeamDataLoader)):
        return loader.load(self.id)

    member_count: int = 0
    def post_member_count(self):
        return sum([t.member_count for t in self.teams])

class Result(BaseModel):
    departments: List[Department]



async def main():
    """
    1. generate data from departments to members  (top to bottom)
    2. use post_method to calc member count of team level and department level
    """
    Result.update_forward_refs()
    department_ids = {1, 2,3}
    departments = [Department(**d) for d in datum.departments if d['id'] in department_ids] 
    result = Result(departments=departments)
    resolver = Resolver()
    data = await resolver.resolve(result)
    print(json.dumps(data.dict(), indent=2))

asyncio.run(main())
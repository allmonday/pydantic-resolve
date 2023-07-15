from __future__ import annotations
import json
import asyncio
from typing import Optional
from pydantic import BaseModel
from pydantic_resolve import Resolver, ensure_subset
from readme_demo.datum import datum, DepartmentBase, TeamBase, MemberBase


def query_by_id(items, id):
    res = [item for item in items if item['id'] == id]
    if res:
        return res[0]
    return None

class Result(BaseModel):
    department: Optional[Department] = None
    async def resolve_department(self, context):
        await asyncio.sleep(1)
        return query_by_id(datum.departments, context['department_id'])

    team: Optional[Team] = None
    async def resolve_team(self, context):
        await asyncio.sleep(1)
        return query_by_id(datum.teams, context['team_id'])

    member: Optional[Member] = None
    async def resolve_member(self, context):
        await asyncio.sleep(1)
        return query_by_id(datum.members, context['member_id'])


@ensure_subset(DepartmentBase)
class Department(BaseModel):
    id: int
    name: str

@ensure_subset(TeamBase)
class Team(BaseModel):
    id: int
    name: str

@ensure_subset(MemberBase)
class Member(BaseModel):
    id: int
    name: str


async def main():
    """
    1. query each single item of department, team and member (no loader)
    """
    result = Result()
    resolver = Resolver(
        annotation_class=Result,
        context={
            'department_id': 0,
            'team_id': 1,
            'member_id': 10,
        })
    data = await resolver.resolve(result)
    print(json.dumps(data.dict(), indent=2))

asyncio.run(main())
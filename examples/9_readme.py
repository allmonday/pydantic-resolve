from __future__ import annotations
import json
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, build_list

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

members = [
  dict(id=1, team_id=1, name="Sophia"),
  dict(id=2, team_id=1, name="Jackson"),
  dict(id=3, team_id=2, name="Olivia"),
  dict(id=4, team_id=2, name="Liam"),
  dict(id=5, team_id=3, name="Emma"),
  dict(id=6, team_id=4, name="Noah"),
  dict(id=7, team_id=5, name="Ava"),
  dict(id=8, team_id=6, name="Lucas"),
  dict(id=9, team_id=6, name="Isabella"),
  dict(id=10, team_id=6, name="Mason"),
  dict(id=11, team_id=7, name="Mia"),
  dict(id=12, team_id=8, name="Ethan"),
  dict(id=13, team_id=8, name="Amelia"),
  dict(id=14, team_id=9, name="Oliver"),
  dict(id=15, team_id=9, name="Charlotte"),
  dict(id=16, team_id=10, name="Jacob"),
  dict(id=17, team_id=10, name="Abigail"),
  dict(id=18, team_id=10, name="Daniel"),
  dict(id=19, team_id=10, name="Emily"),
  dict(id=20, team_id=10, name="Ella")
]

async def teams_batch_load_fn(department_ids):
    return build_list(teams, department_ids, lambda t: t['department_id'])

async def members_batch_load_fn(team_ids):
    return build_list(members, team_ids, lambda t: t['team_id'])


class Result(BaseModel):
    departments: List[Department] = []
    def resolve_departments(self):
        return departments

class Member(BaseModel):
    id: int
    name: str

class Team(BaseModel):
    id: int
    name: str

    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(members_batch_load_fn)):
        return loader.load(self.id)

class Department(BaseModel):
    id: int
    name: str
    teams: List[Team] = []
    def resolve_teams(self, loader=LoaderDepend(teams_batch_load_fn)):
        return loader.load(self.id)

async def main():
    result = Result()
    # data = await Resolver().resolve(result)
    # print(json.dumps(data.dict(), indent=2))

asyncio.run(main())
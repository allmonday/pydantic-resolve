from collections import defaultdict
import json
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend
from aiodataloader import DataLoader
from readme_demo.datum import datum, DepartmentBase, TeamBase, MemberBase


class TeamDummyLoader(DataLoader):
    async def batch_load_fn(self, department_ids):
        return department_ids

class MemberDummyLoader(DataLoader):
    async def batch_load_fn(self, team_ids):
        return team_ids


class Member(MemberBase):
    ...

class Team(TeamBase):
    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(MemberDummyLoader)):
        return loader.load(self.id)

class Department(DepartmentBase):
    teams: List[Team] = []
    def resolve_teams(self, loader=LoaderDepend(TeamDummyLoader)):
        return loader.load(self.id)

class Result(BaseModel):
    departments: List[Department]


def add_to_loader(items, get_id, loader):
    d = defaultdict(list)
    for item in items:
        d[get_id(item)].append(item)

    for k, v in d.items():
        loader.prime(k, v)

def get_uniq_parent_ids(items, get_id):
    d = set()
    for item in items:
        d.add(get_id(item))

    return list(d)


def get_items_by_ids(items, ids):
    return [item for item in items if item['id'] in ids]


async def main():
    """
    1. generate the data from members to departments (bottom to top)
    2. get member > teams > departments
    3. build
    """
    member_loader = MemberDummyLoader()
    team_loader = TeamDummyLoader()

    # get members and add to loader
    member_ids = {1,2,9}
    members = [m for m in datum.members if m['id'] in member_ids]
    add_to_loader(members, lambda x: x['team_id'], member_loader)

    # get parent teams and add to loader
    team_ids = get_uniq_parent_ids(members, lambda x: x['team_id'])
    teams = get_items_by_ids(datum.teams, team_ids)
    add_to_loader(teams, lambda x: x['department_id'], team_loader)

    # get parent departments
    department_ids = get_uniq_parent_ids(teams, lambda x: x['department_id'])
    departments = get_items_by_ids(datum.departments, department_ids)

    result = Result(departments=[Department(**d) for d in departments])
    resolver = Resolver(
        loader_instances={
            TeamDummyLoader: team_loader, 
            MemberDummyLoader: member_loader}
        )
    data = await resolver.resolve(result)
    print(json.dumps(data.dict(), indent=2))

asyncio.run(main())
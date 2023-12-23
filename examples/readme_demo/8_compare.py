from collections import defaultdict
from typing import List
from pydantic import BaseModel
from readme_demo.datum import datum, DepartmentBase, TeamBase, MemberBase





class Member(MemberBase):
    ...

class Team(TeamBase):
    members: List[Member]

class Department(DepartmentBase):
    teams: List[Team]

class Result(BaseModel):
    departments: List[Department]


def main():
    departments = datum.departments
    department_ids = {d['id'] for d in departments}

    teams = [t for t in datum.teams if t['department_id'] in department_ids]
    team_ids = {t['id'] for t in teams}

    members = [m for m in datum.members if m['team_id'] in team_ids]

    # team --> members
    team_members = defaultdict(list)
    for m in members:
        team_members[m['team_id']].append(m)

    for t in teams:
        t['members'] = team_members.get(t['id'], [])

    # department --> teams
    department_teams = defaultdict(list)
    for t in teams:
        department_teams[t['department_id']].append(t)

    for d in departments:
        d['teams'] = department_teams.get(d['id'], [])

    result = Result(departments=departments)
    print(result.json(indent=2))


main()
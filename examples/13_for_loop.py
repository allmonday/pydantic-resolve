import asyncio
from pydantic_resolve import Resolver, ICollector
from pydantic import BaseModel

# get the sum of estimated and done estimated
input = {
    "name": "Team A",
    "sprints": [
        {
            "name": "Sprint 1",
            "stories": [
                {
                    "name": "Story 1",
                    "tasks": [
                        {"name": "Task 1", "estimated": 5, "done": False},
                        {"name": "Task 2", "estimated": 3, "done": True},
                    ]
                },
                {
                    "name": "Story 2",
                    "tasks": [
                        {"name": "Task 3", "estimated": 2, "done": True},
                        {"name": "Task 4", "estimated": 1, "done": True},
                    ]
                }
            ]
        },
        {
            "name": "Sprint 2",
            "stories": [
                {
                    "name": "Story 3",
                    "tasks": [
                        {"name": "Task 5", "estimated": 3, "done": False},
                        {"name": "Task 6", "estimated": 2, "done": False},
                    ]
                },
                {
                    "name": "Story 4",
                    "tasks": [
                        {"name": "Task 7", "estimated": 1, "done": False},
                        {"name": "Task 8", "estimated": 3, "done": False},
                    ]
                }
            ]
        }
    ]
}


class TotalEstimateCollector(ICollector):
    def __init__(self, alias):
        self.alias = alias
        self.counter = 0

    def add(self, val):
        self.counter = self.counter + val

    def values(self):
        return self.counter

class TotalDoneEstimateCollector(ICollector):
    def __init__(self, alias):
        self.alias = alias
        self.counter = 0

    def add(self, val):
        done, estimate = val
        if done:
            self.counter = self.counter + estimate

    def values(self):
        return self.counter

class Task(BaseModel):
    __pydantic_resolve_collect__ = {
        'estimated': 'total_estimate',
        ('done', 'estimated'): 'done_estimate'
    }
    name: str
    estimated: int
    done: bool

class Story(BaseModel):
    name: str
    tasks: list[Task]

    total_estimated: int = 0
    def post_total_estimated(self, counter=TotalEstimateCollector('total_estimate')):
        return counter.values()

    total_done_estimated: int = 0
    def post_total_done_estimated(self, counter=TotalDoneEstimateCollector('done_estimate')):
        return counter.values()

class Sprint(BaseModel):
    name: str
    stories: list[Story]

    total_estimated: int = 0
    def post_total_estimated(self, counter=TotalEstimateCollector('total_estimate')):
        return counter.values()

    total_done_estimated: int = 0
    def post_total_done_estimated(self, counter=TotalDoneEstimateCollector('done_estimate')):
        return counter.values()

class Team(BaseModel):
    name: str
    sprints: list[Sprint]

    total_estimated: int = 0
    def post_total_estimated(self, counter=TotalEstimateCollector('total_estimate')):
        return counter.values()

    total_estimated2: int = 0
    def post_total_estimated2(self, counter=TotalEstimateCollector('total_estimate')):
        return counter.values()

    total_done_estimated: int = 0
    def post_total_done_estimated(self, counter=TotalDoneEstimateCollector('done_estimate')):
        return counter.values()

async def main():
    team = Team.parse_obj(input)
    team = await Resolver().resolve(team)
    print(team.json(indent=4))

asyncio.run(main())
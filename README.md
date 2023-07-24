![img](doc/imgs/resolver.png)

> A small yet powerful package which can run resolvers to generate deep nested datasets.

[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)




[Change log](./changelog.md)


## Install

```shell
pip install pydantic-resolve
```

## Quick start

Assume we have 3 tables: `departments`, `teams` and `members`, which have `1:N relationship` from left to right. 

```python
# 1. prepare table records
departments = [
    dict(id=1, name='INFRA'),
    dict(id=2, name='DevOps'),
    dict(id=3, name='Sales'),
]

teams = [
    dict(id=1, department_id=1, name="K8S"),
    dict(id=2, department_id=1, name="MONITORING"),
    # ...
    dict(id=10, department_id=2, name="Operation"),
]

members = [
    dict(id=1, team_id=1, name="Sophia"),
    # ...
    dict(id=19, team_id=10, name="Emily"),
    dict(id=20, team_id=10, name="Ella")
]
```

and we want to generate nested json base on these 3 tables. the output should be looks like: 

> and we hope to query each table for only once, N+1 query is forbidden.

```json
{
  "departments": [
    {
      "id": 1,
      "name": "INFRA",
      "teams": [
        {
          "id": 1,
          "name": "K8S",
          "members": [
            {
              "id": 1,
              "name": "Sophia"
            }
          ]
        }
      ]
    }
  ]
}
```

We will shows how to make it with `pydantic-resolve` which has 4 steps:

1. get data
2. group children with parent_id in dataloader function
3. define pydantic schema, bind with dataloader
4. resolve



```python
import json
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, build_list

# 1. prepare table records
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

# 2. define dataloader
async def teams_batch_load_fn(department_ids):
    """ return teams grouped by department_id """
    return build_list(teams, department_ids, lambda t: t['department_id'])

async def members_batch_load_fn(team_ids):
    """ return members grouped by team_id """
    return build_list(members, team_ids, lambda t: t['team_id'])

# 3. define pydantic types
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

class Result(BaseModel):
    departments: List[Department] = []
    def resolve_departments(self):
        return departments

async def main():
    result = Result()
    # 4. resolve
    data = await Resolver().resolve(result)
    print(json.dumps(data.dict(), indent=4))

asyncio.run(main())
```

then we got:

```json
{
  "departments": [
    {
      "id": 1,
      "name": "INFRA",
      "teams": [
        {
          "id": 1,
          "name": "K8S",
          "members": [
            {
              "id": 1,
              "name": "Sophia"
            },
            {
              "id": 2,
              "name": "Jackson"
            }
          ]
        },
        {
          "id": 2,
          "name": "MONITORING",
          "members": [
            {
              "id": 3,
              "name": "Olivia"
            },
            {
              "id": 4,
              "name": "Liam"
            }
          ]
        },
        {
          "id": 3,
          "name": "Jenkins",
          "members": [
            {
              "id": 5,
              "name": "Emma"
            }
          ]
        }
      ]
    },
    {
      "id": 2,
      "name": "DevOps",
      "teams": [
        {
          "id": 5,
          "name": "Frontend",
          "members": [
            {
              "id": 7,
              "name": "Ava"
            }
          ]
        },
        {
          "id": 6,
          "name": "Bff",
          "members": [
            {
              "id": 8,
              "name": "Lucas"
            },
            {
              "id": 9,
              "name": "Isabella"
            },
            {
              "id": 10,
              "name": "Mason"
            }
          ]
        },
        {
          "id": 7,
          "name": "Backend",
          "members": [
            {
              "id": 11,
              "name": "Mia"
            }
          ]
        }
      ]
    },
    {
      "id": 3,
      "name": "Sales",
      "teams": [
        {
          "id": 8,
          "name": "CAT",
          "members": [
            {
              "id": 12,
              "name": "Ethan"
            },
            {
              "id": 13,
              "name": "Amelia"
            }
          ]
        },
        {
          "id": 9,
          "name": "Account",
          "members": [
            {
              "id": 14,
              "name": "Oliver"
            },
            {
              "id": 15,
              "name": "Charlotte"
            }
          ]
        },
        {
          "id": 10,
          "name": "Operation",
          "members": [
            {
              "id": 16,
              "name": "Jacob"
            },
            {
              "id": 17,
              "name": "Abigail"
            },
            {
              "id": 18,
              "name": "Daniel"
            },
            {
              "id": 19,
              "name": "Emily"
            },
            {
              "id": 20,
              "name": "Ella"
            }
          ]
        }
      ]
    }
  ]
}
```

## More cases:

for more cases like: 
- how to filter members
- how to make post calculation after resolved?
- and so on..

please read the following demos.

```shell
cd examples

python -m readme_demo.0_basic
python -m readme_demo.1_filter
python -m readme_demo.2_post_methods
python -m readme_demo.3_context
python -m readme_demo.4_loader_instance
python -m readme_demo.5_subset
python -m readme_demo.6_mapper
python -m readme_demo.7_single
```


## API

### Resolver(loader_filters, loader_instances, ensure_type, annotation_class, context)

- loader_filters: `dict`

  provide extra query filters along with loader key.

  reference: [6_sqlalchemy_loaderdepend_global_filter.py](examples/6_sqlalchemy_loaderdepend_global_filter.py) L55, L59

- loader_instances: `dict`

  provide pre-created loader instance, with can `prime` data into loader cache.

  reference: [test_20_loader_instance.py](tests/resolver/test_20_loader_instance.py), L62, L63

- ensure_type: `bool`

  if `True`, resolve method is restricted to be annotated.

  reference: [test_13_check_wrong_type.py](tests/resolver/test_13_check_wrong_type.py)

- annotation_class: `class`

  if you have `from __future__ import annotation`, and pydantic raises error, use this config to update forward refs

  reference: [test_25_parse_to_obj_for_pydantic_with_annotation.py](tests/resolver/test_25_parse_to_obj_for_pydantic_with_annotation.py), L39

- context: `dict`

  context can carry setting into each single resolver methods.

  ```python

  class Earth(BaseModel):
      humans: List[Human] = []
      def resolve_humans(self, context):
          return [dict(name=f'man-{i}') for i in range(context['count'])]

  earth = await Resolver(context={'count': 10}).resolve(earth)
  ```

### LoaderDepend(loader_fn)

- loader_fn: `subclass of DataLoader or batch_load_fn`. [detail](https://github.com/syrusakbary/aiodataloader#dataloaderbatch_load_fn-options)

  declare dataloader dependency, `pydantic-resolve` will take the care of lifecycle of dataloader.

### build_list(rows, keys, fn), build_object(rows, keys, fn)

- rows: `list`, query result
- keys: `list`, batch_load_fn:keys
- fn: `lambda`, define the way to get primary key

  helper function to generate return value required by `batch_load_fn`. read the code for details.

  reference: [test_utils.py](tests/utils/test_utils.py), L32

### mapper(param)

- param: `class of pydantic or dataclass, or a lambda`

  `pydantic-resolve` will trigger the fn in `mapper` after inner future is resolved. it exposes an interface to change return schema even from the same dataloader.
  if param is a class, it will try to automatically transform it.

  reference: [test_16_mapper.py](tests/resolver/test_16_mapper.py)


### ensure_subset(base_class)

- base_class: `class`

  it will raise exception if fields of decorated class has field not existed in `base_class`.

  reference: [test_2_ensure_subset.py](tests/utils/test_2_ensure_subset.py)


## Run FastAPI example

```shell
poetry shell
cd examples
uvicorn fastapi_demo.main:app
# http://localhost:8000/docs#/default/get_tasks_tasks_get
```


## Unittest

```shell
poetry run python -m unittest  # or
poetry run pytest  # or
poetry run tox
```

## Coverage

```shell
poetry run coverage run -m pytest
poetry run coverage report -m
```

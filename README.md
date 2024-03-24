[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

Pydantic-resolve is a schema based, hierarchical solution for fetching and crafting data.

It combines the advantages of restful and graphql.
![img](docs/images/intro.jpeg)


Advantages:
1. use declaretive way to define view data, easy to maintain and develop
2. enhance the traditional restful response, to support gql-like style data structure.
3. provide post_method and other tools to craft resolved data.


[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)

## Install

> If you are using pydantic v2, please use [pydantic2-resolve](https://github.com/allmonday/pydantic2-resolve) instead.


```shell
pip install pydantic-resolve
```


## API Reference
https://allmonday.github.io/pydantic-resolve/reference_api/

## Composition oriented development-pattern (wip)
https://github.com/allmonday/composition-oriented-development-pattern


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

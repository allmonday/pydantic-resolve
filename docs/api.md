# API

## Methods

### resolve

`resolve_<field>` methods can be async. `Resolver` will recursively execute `resolve_<field>` methods on child nodes to fetch data.

```python
class Blog(BaseModel):
	id: int

	comments: list[str] = []
	def resolve_comments(self):
		return ['comment-1', 'comment-2']

	tags: list[str] = []
	async def resolve_tags(self):
		await asyncio.sleep(1)
		return ['tag-1', 'tag-2']
```

Supported parameters:

- `context`: global context, set on `Resolver`
- `ancestor_context`: local context, configured in `__pydantic_resolve_expose__`
- `parent`: parent node
- `dataloader`: you can declare multiple dataloaders, e.g. `loader=Loader(SomeLoader), loader_b=Loader(AnotherLoader)`


### post

`post_<field>` methods can be sync or async. They run after the data of descendants is fully processed, and are used for post-processing the resolved data.

```python
class Blog(BaseModel):
	id: int

	comments: list[str] = []
	def resolve_comments(self):
		return ['comment-1', 'comment-2']

	def post_comments(self):
		return self.comments[-1:] # keep the last one
```

Supported parameters:

- `context`: global context, set on `Resolver`
- `ancestor_context`: local context, configured in `__pydantic_resolve_expose__`
- `parent`: parent node
- `dataloader`: you can declare multiple dataloaders, e.g. `loader=Loader(SomeLoader), loader_b=Loader(AnotherLoader)`
  - Note: objects returned from `post` will NOT be recursively resolved again. This is different from `resolve`.
- `collector`: you can declare multiple collectors, e.g. `collector_a=Collector('a'), collector_b=Collector('b')`


### post_default_handler

`post_default_handler` is a special post method. It runs after all other post methods have finished. It is useful for cleanup or finalization logic.

Note: it does not do any automatic assignment. You must set fields manually.

```python
class Blog(BaseModel):
	id: int

	length: int

	def post_default_handler(self):
		self.length = 100
```

Supported parameters:

- `context`: global context, set on `Resolver`
- `ancestor_context`: local context, configured in `__pydantic_resolve_expose__`
- `parent`: parent node
- `collector`: you can declare multiple collectors, e.g. `collector_a=Collector('a'), collector_b=Collector('b')`

## Resolver

The entry point of `pydantic-resolve`.

```python

class Resolver:
	def __init__(
			self,
			loader_params: Optional[Dict[Any, Dict[str, Any]]] = None,
			global_loader_param: Optional[Dict[str, Any]] = None,
			loader_instances: Optional[Dict[Any, Any]] = None,
			context: Optional[Dict[str, Any]] = None
			debug: bool = False
			enable_from_attribute_in_type_adapter = False,
			annotation: Optional[Type[T]] = None
			):
```

### loader_params

Provide parameters for DataLoaders.

```python
resolver = Resolver(loader_params={ LoaderA: { "param_x": 1, "param_y": 2 } })
```

### global_loader_param

Set DataLoader parameters globally. This can be convenient in some cases.

```python
resolver = Resolver(global_loader_param={ { "param_x": 1, "param_y": 2 } })
```

If parameters come from multiple sources:

```python
resolver = Resolver(
	loader_params={ LoaderA: { "param_x": 2 } },
	global_loader_param={ { "param_x": 1, "param_y": 2 } })
```

it will raise an error.

### loader_instances

You can pass DataLoader instances (for example, pre-primed with data).

```python
loader = LoaderA()
loader.prime('a', [1,2,3])
resolver = Resolver(loader_instances={ LoaderA: loader })
```

### context

Provide global context. It is accessible in all `resolve_*` and `post_*` methods.

```python
resolver = Resolver(context={'name': 'tangkikodo'})
```

### debug

When `debug=True`, the logger prints the total elapsed time per node.

> `export PYDANTIC_RESOLVE_DEBUG=true` enables it globally.

```shell
# sample
Tree          : avg: 1.1ms, max: 1.1ms, min: 1.1ms
Tree.Tree     : avg: 0.4ms, max: 0.5ms, min: 0.4ms
Tree.Tree.Tree: avg: 0.2ms, max: 0.2ms, min: 0.2ms

# sample
MyBlogSite             : avg: 1.5ms, max: 1.5ms, min: 1.5ms
MyBlogSite.Blog        : avg: 1.0ms, max: 1.0ms, min: 1.0ms
MyBlogSite.Blog.Comment: avg: 0.3ms, max: 0.3ms, min: 0.3ms
```

### enable_from_attribute_in_type_adapter (pydantic v2)

Only for pydantic v2. It mainly solves (as a fallback) potential upgrade issues from v1.

> `export PYDANTIC_RESOLVE_ENABLE_FROM_ATTRIBUTE=true` enables it globally.

In v1, converting from a Pydantic object that is NOT the target field type (but still has the required fields) can work via `parse_obj_as`. In v2, `TypeAdapter` will raise an error.

```python
class A(BaseModel):
  name: str
  id: int

class B(BaseModel):
  name: str
```

In v2, you can use `typeAdapter.validate_python(data, from_attribute=True)` as a fallback. But it can add 10%+ overhead for conversions, so the default is `False`. Enable it only when needed.

### annotation

Specify the root type when resolving. When the input data is a list of `Union` types, the root type cannot be inferred automatically; use this parameter to set it explicitly.


## ErDiagram

ErDiagram allows you to declare application-level entity relationships at the domain model level, then automatically generate resolve methods based on these relationships.

### Core Classes

#### Relationship

Defines a single relationship between two entities.

```python
from pydantic_resolve import Relationship

class User(BaseModel):
    id: int
    name: str

class Comment(BaseModel):
    id: int
    user_id: int

    # Define relationship: load User via user_id
    __relationships__ = [
        Relationship(
            fk='user_id',
            target=User,
            name='user',
            loader=user_loader
        )
    ]
```

**Parameters:**

- `fk` (str): The foreign key field name
- `target` (type): The target Pydantic model class
- `name` (str): **REQUIRED**. Unique identifier for this relationship, becomes the GraphQL field name
- `loader` (Callable | None): DataLoader function to fetch the target entity
- `fk_fn` (Callable | None): Optional function to transform the FK value before passing to loader
- `fk_none_default` (Any | None): Default value to return if FK is None
- `fk_none_default_factory` (Callable | None): Factory function to create default value if FK is None
- `load_many` (bool): Whether the FK field itself contains multiple values (e.g., `user_ids: list[int]`), causing `loader.load_many()` to be called instead of `loader.load()` (default: False)
- `load_many_fn` (Callable | None): Optional function to transform the FK field value into an iterable for `load_many`

**Note:** `MultipleRelationship` and `Link` have been removed in favor of a simplified flat `Relationship` model. To define multiple relationships from the same field, simply define multiple `Relationship` objects with unique `name` values.

#### Multiple Relationships from Same Field

To define multiple relationships from the same foreign key field, create multiple `Relationship` objects with different `name` values:

```python
from pydantic_resolve import Relationship

class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int
    moderator_id: int

    # Define two relationships via user_id: author and moderator
    __relationships__ = [
        Relationship(
            fk='user_id',
            target=User,
            name='author',  # GraphQL field name for this relationship
            loader=user_loader
        ),
        Relationship(
            fk='user_id',
            target=User,
            name='moderator',  # Different GraphQL field name
            loader=moderator_loader
        )
    ]
```

#### Entity

Defines entity metadata including its relationships.

```python
from pydantic_resolve import Entity

Entity(
    kls=Comment,
    relationships=[
        Relationship(fk='user_id', target=User, name='user', loader=user_loader)
    ]
)
```

**Parameters:**

- `kls` (type[BaseModel]): The Pydantic model class
- `relationships` (list[Relationship]): List of relationships

#### ErDiagram

Container for all entity relationship definitions.

```python
from pydantic_resolve import ErDiagram

ErDiagram(
    configs=[
        Entity(kls=Comment, relationships=[...]),
        Entity(kls=User, relationships=[...])
    ],
    description="My application ERD"
)
```

**Parameters:**

- `configs` (list[Entity]): List of entity definitions
- `description` (str | None): Optional description of the diagram

#### Usage

To use an `ErDiagram` with the Resolver, you need to register it using either `config_resolver()` or `config_global_resolver()`:

- `config_resolver(diagram)`: Creates a new custom Resolver class with the ERD
- `config_global_resolver(diagram)`: Injects the ERD into the default Resolver class globally

See the [Helper Functions](#helper-functions) section below for detailed usage examples.

### Helper Functions

#### base_entity()

Creates a base class that automatically collects all entity relationships from its subclasses.

**Note:** `BaseEntity` provides an alternative ERD declaration approach compared to explicitly creating `ErDiagram` objects. This method is more tightly integrated with your entity classes, making it easier to manage relationships directly within the class definitions.

```python
from pydantic_resolve import base_entity, Relationship

BaseEntity = base_entity()

class User(BaseModel, BaseEntity):
    id: int
    name: str

    __relationships__ = [
        Relationship(fk='org_id', target=Organization, name='organization', loader=org_loader)
    ]

class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int

    __relationships__ = [
        Relationship(fk='user_id', target=User, name='user', loader=user_loader)
    ]

# Get the ER diagram
diagram = BaseEntity.get_diagram()
```

**Handling Circular Imports**

Because entities reference each other through `target_kls`, you may encounter circular import issues. There are two solutions:

1. **Use string references** (for same-module references):
   ```python
   class Comment(BaseModel, BaseEntity):
       id: int
       user_id: int

       __relationships__ = [
           # String 'User' will be resolved automatically
           Relationship(fk='user_id', target='User', name='user', loader=user_loader)
       ]
   ```

2. **Use module path syntax** (for cross-module references):
   ```python
   # In app/models/comment.py

   class Comment(BaseModel, BaseEntity):
       id: int
       user_id: int

       __relationships__ = [
           # Reference User from another module
           Relationship(
               fk='user_id',
               target='app.models.user:User',  # module.path:ClassName
               name='user',
               loader=user_loader
           )
       ]
   ```

The `_resolve_ref` function supports:

- Simple class names: `'User'` (looked up in the current module)
- Module path syntax: `'app.models.user:User'` (lazy import from any module)
- List generics: `list['User']` or `list['app.models.user:User']`

#### AutoLoad

Annotation to automatically resolve fields based on ERD relationships. `AutoLoad` is created from an `ErDiagram` instance via `create_auto_load()`.

```python
from pydantic_resolve import base_entity, config_global_resolver

# 1. Define entities with BaseEntity
BaseEntity = base_entity()

class User(BaseModel, BaseEntity):
    id: int
    name: str
    org_id: int
    __relationships__ = [
        Relationship(fk='org_id', target=Organization, name='organization', loader=org_loader)
    ]
```

2. Register ERD globally and create AutoLoad

```python
config_global_resolver(BaseEntity.get_diagram())
AutoLoad = BaseEntity.get_diagram().create_auto_load()
```

3. Use AutoLoad in response models

```python
class UserResponse(BaseModel):
    id: int
    name: str
    org_id: int

    # Field name matches Relationship.name, auto-resolves via ERD
    organization: Annotated[Optional[Organization], AutoLoad()] = None
```

**Parameters:**

- `origin` (str | None): The `name` of the target Relationship to look up. Defaults to `None`, in which case the annotated field name is used as the lookup key.

**Note:** `AutoLoad` works with `config_global_resolver()` to inject the ERD into the default Resolver.

#### config_resolver()

Creates a new Resolver class with specific ERD configuration.

```python
from pydantic_resolve import config_resolver, ErDiagram, Entity

diagram = ErDiagram(configs=[...])
CustomResolver = config_resolver(diagram)

result = await CustomResolver().resolve(data)
```

#### Relationship Configuration Examples

**Basic Relationship (to-one):**

```python
Relationship(
    fk='user_id',
    target=User,
    name='user',
    loader=user_loader
)
```

**To-Many Relationship:**

```python
Relationship(
    fk='tag_ids',
    target=Tag,
    name='tags',
    loader=tag_loader,
    load_many=True,
    load_many_fn=lambda ids: ids.split(',') if ids else []
)
```

**Handling None FK Values:**

```python
# Return None when FK is None
Relationship(
    fk='user_id',
    target=User,
    name='user',
    loader=user_loader,
    fk_none_default=None
)

# Or use a factory to return a default object
Relationship(
    fk='user_id',
    target=User,
    name='user',
    loader=user_loader,
    fk_none_default_factory=lambda: AnonymousUser()
)
```

**Multiple Relationships from Same Field:**

```python
class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int

    __relationships__ = [
        Relationship(
            fk='user_id',
            target=User,
            name='author',
            loader=user_loader
        ),
        Relationship(
            fk='user_id',
            target=User,
            name='moderator',
            loader=moderator_loader
        )
    ]

class CommentResponse(BaseModel):
    id: int
    user_id: int

    author: Annotated[Optional[User], AutoLoad()] = None
    moderator: Annotated[Optional[User], AutoLoad()] = None
```

#### config_global_resolver()

Injects an ERD into the default Resolver class globally.

```python
from pydantic_resolve import config_global_resolver, base_entity

BaseEntity = base_entity()
# ... define entities ...

config_global_resolver(BaseEntity.get_diagram())

# Now default Resolver will use the ERD
result = await Resolver().resolve(data)
```


## DefineSubset & SubsetConfig

`DefineSubset` allows you to create a subset of fields from an existing Pydantic model, inheriting types and validators.

### Basic Usage

```python
from pydantic_resolve import DefineSubset

class FullUser(BaseModel):
    id: int
    name: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime

class UserSummary(DefineSubset):
    __subset__ = (FullUser, ('id', 'name', 'email'))
```

### Using SubsetConfig

For more control, use `SubsetConfig`:

```python
from pydantic_resolve import DefineSubset, SubsetConfig
from pydantic_resolve import ExposeAs, SendTo

class UserProfile(DefineSubset):
    __subset__ = SubsetConfig(
        kls=FullUser,
        fields=['id', 'name', 'email'],
        expose_as=[('name', 'user_name')],  # Expose to descendants
        send_to=[('id', 'user_id_collector')],  # Send to parent's collector
        excluded_fields=['email']  # Mark as excluded from serialization
    )
```

**SubsetConfig Parameters:**

- `kls` (type[BaseModel]): The parent class to subset from
- `fields` (list[str] | "all" | None): Fields to include (mutually exclusive with omit_fields)
- `omit_fields` (list[str] | None): Fields to exclude (mutually exclusive with fields)
- `expose_fields` (list[str] | None): Fields to expose to descendants via ExposeAs
- `excluded_fields` (list[str] | None): Fields to mark as excluded (Field(exclude=True))


## ExposeAs & SendTo

Starting from v2.3.0, you can use annotations instead of class attributes for expose and collect.

### ExposeAs

Expose field data to descendant nodes.

```python
from pydantic_resolve import ExposeAs

# Before (class attribute)
class Blog(BaseModel):
    __pydantic_resolve_expose__ = {'title': 'blog_title' }
    title: str

# After (annotation)
class Blog(BaseModel):
    title: Annotated[str, ExposeAs('blog_title')]
```

### SendTo

Send field data to parent node's collector.

```python
from pydantic_resolve import SendTo

# Before (class attribute)
class Blog(BaseModel):
    __pydantic_resolve_collect__ = {'comments': 'blog_comments' }
    comments: list[Comment]

# After (annotation)
class Blog(BaseModel):
    comments: Annotated[list[Comment], SendTo('blog_comments')]
```

### Combining Both

You can combine multiple annotations:

```python
from pydantic_resolve import ExposeAs, SendTo

# AutoLoad = diagram.create_auto_load()

class Comment(BaseModel):
    owner: Annotated[
        Optional[User],
        AutoLoad('user_id'),      # Auto-resolve via ERD
        SendTo('related_users') # Send to parent's collector
    ] = None

class Blog(BaseModel):
    name: Annotated[str, ExposeAs('blog_name')]  # Expose to descendants
```


## Method Parameter Reference

### context

`context` is a global context set on `Resolver`, and can be accessed by all methods.

```python hl_lines="5 9"
class Blog(BaseModel):
	id: int

	comments: list[str] = []
	def resolve_comments(self, context):
		prefix = context['prefix']
		return [f'{prefix}-{c}' for c in ['comment-1', 'comment-2']]

	def post_comments(self, context):
		limit = context['limit']
		return self.comments[-limit:]  # get last [limit] comments

blog = Blog(id=1)
blog = await Resolver(context={'prefix': 'my', 'limit': 1}).resolve(blog)
```

### ancestor_context

Sometimes you want to read data from ancestor nodes. Use `ancestor_context` for that.

First, add `__pydantic_resolve_expose__` on the ancestor node to expose field names and aliases (to avoid collisions across levels).

Then you can read them from `ancestor_context`.

```python hl_lines="2 18"
class Blog(BaseModel):
	__pydantic_resolve_expose__ = {'title': 'blog_title' }
	id: int
	title: str

	comments: list[Comment] = []
	def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
		return loader.load(self.id)

	comment_count: int = 0
	def post_comment_count(self):
		return len(self.comments)

class Comment(BaseModel):
	id: int
	content: str
	def post_content(self, ancestor_context):
		blog_title = ancestor_context['blog_title']
		return f'[{blog_title}] - {self.content}'
```

**Starting from v2.3.0, `ExposeAs` can replace `__pydantic_resolve_expose__`**, they are exclusive

```python
from pydantic_resolve import ExposeAs

class Blog(BaseModel):
    # __pydantic_resolve_expose__ = {'title': 'blog_title' }
    id: int
    title: Annotated[str, ExposeAs('blog_title')]
```

### parent

You can access the direct parent node. This is especially useful for tree-like structures.

```python hl_lines="6-8"
class Tree(BaseModel):
	name: str
	children: List[Tree] = []

	path: str = ''
	def resolve_path(self, parent):
		if parent is not None:
			return f'{parent.path}/{self.name}'
		return self.name

data = dict(name="a", children=[
	dict(name="b", children=[
		dict(name="c")
	]),
	dict(name="d", children=[
		dict(name="c")
	])
])
data = await Resolver().resolve(Tree(**data))
```

### collector

`collector` lets you gather data across generations. It works with `Collector` and `__pydantic_resolve_collect__`.

On descendant nodes, define `__pydantic_resolve_collect__` to specify which fields to provide and the collector alias.

With `collector`, you can reshape data without manually looping and flattening all descendants.

For example, you can collect comment data from each blog at the top-level schema.

```python hl_lines="13 18"
form pydantic_resolve import Collector

class MyBlogSite(BaseModel):
	blogs: list[Blog] = []
	async def resolve_blogs(self):
		return await get_blogs()

	comment_count: int = 0
	def post_comment_count(self):
		return sum([b.comment_count for b in self.blogs])

	all_comments: list[Comment] = []
	def post_all_comments(self, collector=Collector(alias='blog_comments', flat=True)):
		return collector.values()

class Blog(BaseModel):
	__pydantic_resolve_expose__ = {'title': 'blog_title' }
	__pydantic_resolve_collect__ = {'comments': 'blog_comments' }
	id: int
	title: str

	comments: list[Comment] = []
	def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
		return loader.load(self.id)

	comment_count: int = 0
	def post_comment_count(self):
		return len(self.comments)

class Comment(BaseModel):
	id: int
	content: str
	def post_content(self, ancestor_context):
		blog_title = ancestor_context['blog_title']
		return f'[{blog_title}] - {self.content}'
```

Notes:

1. You can create multiple collectors.
2. `Collector` uses a list internally to accumulate values. With `flat=True`, it uses `extend` to merge lists.
3. You can implement your own collector by inheriting from `ICollector`.

```python
from pydantic_resolve import ICollector

class CounterCollector(ICollector):
	def __init__(self, alias):
		self.alias = alias
		self.counter = 0

	def add(self, val):
		self.counter = self.counter + len(val)

	def values(self):
		return self.counter
```

`collector` can only be used in `post` and `post_default_handler`.

- In `post`, you can collect descendant data from resolved fields or other object fields.
- In `post_default_handler`, you can additionally collect descendant data from values returned by `post` methods.

** starting from v2.3.0, `SendTo` can replace __pydantic_resolve_collect__`**, they are exclusive.

```python
from pydantic_resolve import ExposeAs, SendTo

class Blog(BaseModel):
    # __pydantic_resolve_expose__ = {'title': 'blog_title' }
    # __pydantic_resolve_collect__ = {'comments': 'blog_comments' }
    id: int
    title: Annotated[str, ExposeAs('blog_title')]

    comments: Annotated[list[Comment], SendTo('blog_comments')] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
```

### dataloader

DataLoader can batch multiple concurrent async queries into a single request.

In `pydantic-resolve`, use `LoaderDepend` to manage DataLoaders.

> Since v1.12.5, you can also use `Loader`. They are equivalent.

You can declare multiple DataLoaders in a single method.

```python
from pydantic_resolve import LoaderDepend

class Blog(BaseModel):
	id: int
	title: str

	comments: list[Comment] = []
	async def resolve_comments(self,
						 loader1=LoaderDepend(blog_to_comments_loader),
						 loader2=LoaderDepend(blog_to_comments_loader2)):
		v1 = await loader1.load(self.id)  # list
		v2 = await loader2.load(self.id)  # list
		return v1 + v2
```

If a DataLoader defines class variables, you can pass parameters from `Resolver`.

```python hl_lines="2 7"
class LoaderA(DataLoader):
	power: int
	async def batch_load_fn(self, keys: List[int]):
		return [ k** self.power for k in keys ]

data = await Resolver(loader_filters={LoaderA:{'power': 2}}).resolve(data)
```

If multiple DataLoaders of the same type use the same params, you can use `global_loader_param` to reduce boilerplate.

Use it carefully: global params can make configuration harder to reason about.

#### self._query_meta

It provides two pieces of information: `fields` and `request_types`. They describe the type info used after calling the dataloader.

This can help you narrow down the selected fields in the dataloader (e.g. SQL `SELECT` columns).

Because a single dataloader may be called by multiple request types, `request_types` is a list.

`fields` is the de-duplicated union of all `request_types.fields`.

```python
class SampleLoader(DataLoader):
	async def batch_load_fn(self, keys):
		print(self._query_meta['fields']) # => ['id', 'name']
		print(self._query_meta['request_types']) # => [ {'name': Student, 'fields': ['id', 'name'] } ]

		data = await query_students(self._query_meta['fields'], keys)
		# select id, name from xxxxx

		return build_list(data, keys, lambda d: d.id)

class Student(BaseModel):
	id: int
	name: str

class ClassRoom(BaseModel):
	id: int
	name: str

	students: List[Student] = []
	def resolve_students(self, loader=LoaderDepend(SampleLoader)):
		return loader.load(self.id)
```

#### self._context

DataLoaders can access the global context from Resolver by declaring a `_context` attribute. This is useful for scenarios like permission filtering where you need to pass user information.

```python
from aiodataloader import DataLoader

class UserLoader(DataLoader):
    _context: dict  # Declare _context to receive Resolver's context

    async def batch_load_fn(self, keys):
        user_id = self._context.get('user_id')
        # Use user_id for permission filtering
        users = await query_users_with_permission(keys, user_id)
        return users

class TaskResponse(BaseModel):
    id: int
    owner_id: int
    owner: Optional[User] = None

    def resolve_owner(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.owner_id)

# Provide context to Resolver
resolver = Resolver(context={'user_id': 123})
result = await resolver.resolve(tasks)
```

If a DataLoader declares `_context` but Resolver doesn't provide context, a `LoaderContextNotProvidedError` will be raised.

## Helper Utilities

### build_list, build_object

Used in a DataLoader to group fetched records by `keys`.

`build_list` returns a list of objects; `build_object` returns a single object.

Signature: `build_list(data, keys, lambda d: d.key)`

### model_config

> **Deprecated**: This decorator is deprecated. Use `serialization` instead for better handling of nested Pydantic models.

This decorator improves some web frameworks (like FastAPI) when generating JSON schema from `response_model`.

Using `exclude=True` can remove a field during Pydantic conversion, but in FastAPI-generated `openapi.json`, the field (e.g. `name`) may still appear in the schema definition. Adding the `model_config()` decorator can remove `name` from the schema.

Signature: `model_config(default_required=True)`

```python
@model_config()
class Data(BaseModel):
	name: str = Field(default='', exclude=True)
```

```python
from pydantic.dataclasses import dataclass

@dataclass
class Car:
	name: str
	used_years: int = field(default=0, metadata={'exclude': True})
```

Note: if you use pydantic v2 in FastAPI, FastAPI already handles similar behavior internally, so you may not need `model_config`.

### serialization

Decorator to recursively process nested Pydantic BaseModel fields in JSON schema.

This is the recommended replacement for `model_config`. It handles:
- Single level nesting
- Multi-level nesting (3+ levels)
- List nesting (`List[Model]`)
- Optional fields (`Optional[Model]` or `Model | None`)
- Recursive field exclusion (`exclude=True`)

Only needs to be applied to the root class; it automatically processes all nested models.

```python
from pydantic_resolve import serialization
from typing import List, Optional

class Address(BaseModel):
    street: str = ''
    city: str = ''

class Person(BaseModel):
    name: str = ''
    address: Optional[Address] = None

@serialization
class Response(BaseModel):
    person: Person
    items: List[Item]

# Generate schema
schema = Response.model_json_schema(mode='serialization')
```

**Key differences from `model_config`:**
- Automatically processes nested Pydantic models recursively
- Only needs to be applied to the root class
- Handles complex nesting scenarios (List, Optional, multi-level)
- Properly sets `required` fields and excludes `exclude=True` fields at all levels

### ensure_subset

Signature: `ensure_subset(base_kls)`

If you only need a subset of fields but want to strictly ensure it is a valid subset, use `ensure_subset`.

If the base model changes and a field is no longer present, it raises `AttributeError`.

```python
class Base(BaseModel):
	a: str
	b: int

@ensure_subset(Base)
class ChildA(BaseModel):
	a: str
```

### mapper

Provides a conversion/mapping decorator.

```python
class Data(BaseModel):
	id: int

	items: List[Item] = []

	@mapper(lambda x: do_some_conversion(x))
	def resolve_items(self, loader=LoaderDepend(ItemLoader)):
		return loader.load(self.id)
```

### copy_dataloader_kls

Copy a DataLoader class. Useful when you need multiple parameterized DataLoaders with different parameters.

```python
NewLoader = copy_dataloader_kls('NewLoader', OriginLoader)
```

## MCP Server

pydantic-resolve provides MCP (Model Context Protocol) server support, allowing AI agents to discover and interact with GraphQL APIs through progressive disclosure.

### create_mcp_server

Creates an MCP server that exposes multiple ErDiagram applications as independent GraphQL endpoints.

```python
from pydantic_resolve import create_mcp_server, AppConfig

mcp = create_mcp_server(
    apps: List[AppConfig],
    name: str = "Pydantic-Resolve GraphQL API",
) -> "FastMCP"
```

**Parameters:**

- `apps` (list[AppConfig]): List of application configurations. Each config includes:
  - `name`: Application name (required)
  - `er_diagram`: ErDiagram instance (required)
  - `description`: Application description (optional)
  - `query_description`: Query type description (optional)
  - `mutation_description`: Mutation type description (optional)
  - `enable_from_attribute_in_type_adapter`: Enable Pydantic from_attributes mode (default: False)
- `name` (str): MCP server name (default: "Pydantic-Resolve GraphQL API")

**Returns:**

A configured FastMCP server instance ready to run.

**Example:**

```python
from pydantic_resolve import base_entity, config_global_resolver, create_mcp_server, AppConfig

# Define entities
BaseEntity = base_entity()

class User(BaseModel, BaseEntity):
    id: int
    name: str

class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int
    __relationships__ = [
        Relationship(fk='user_id', target=User, name='user', loader=user_loader)
    ]

config_global_resolver(BaseEntity.get_diagram())

# Create MCP server with multiple apps
apps = [
    AppConfig(
        name="blog",
        er_diagram=BaseEntity.get_diagram(),
        description="Blog system with users and posts",
    ),
    AppConfig(
        name="shop",
        er_diagram=shop_diagram,
        description="E-commerce system",
    )
]

mcp = create_mcp_server(apps=apps, name="My API")

# Run the server
mcp.run(transport="streamable-http", port=8080)
```

### AppConfig

Configuration class for a GraphQL application in MCP server.

```python
from pydantic_resolve import AppConfig

AppConfig(
    name: str,                    # Application name (required)
    er_diagram: ErDiagram,        # ErDiagram instance (required)
    description: str | None = None,
    query_description: str | None = None,
    mutation_description: str | None = None,
    enable_from_attribute_in_type_adapter: bool = False,
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Application name used to identify the GraphQL endpoint |
| `er_diagram` | ErDiagram | ErDiagram instance containing entity definitions |
| `description` | str \| None | Optional application description |
| `query_description` | str \| None | Optional description for the Query type |
| `mutation_description` | str \| None | Optional description for the Mutation type |
| `enable_from_attribute_in_type_adapter` | bool | Enable Pydantic from_attributes mode, allows loaders to return Pydantic instances instead of dictionaries |

### Running the MCP Server

The `mcp.run()` method from FastMCP supports multiple transport modes:

```python
# HTTP transport with custom port
mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)

# SSE (Server-Sent Events) transport
mcp.run(transport="sse", port=8080)

# stdio transport (for Claude Desktop, no port needed)
mcp.run(transport="stdio")
```

**Common Parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `transport` | Transport mode: `"stdio"`, `"streamable-http"`, `"sse"` | `"stdio"` |
| `host` | Host address to bind | `"127.0.0.1"` |
| `port` | Port number | `8000` |

### Progressive Disclosure Layers

The MCP server implements progressive disclosure for AI agents:

- **Layer 0**: `list_apps` - Discover available applications
- **Layer 1**: `list_queries`, `list_mutations` - List available operations
- **Layer 2**: `get_query_schema`, `get_mutation_schema` - Get detailed schema information
- **Layer 3**: `graphql_query`, `graphql_mutation` - Execute GraphQL operations

This allows AI agents to incrementally explore and interact with the GraphQL API without being overwhelmed by the full schema at once.

## Exceptions

- `ResolverTargetAttrNotFound`: target field does not exist
- `LoaderFieldNotProvidedError`: required Loader parameters are not provided in `resolve`
- `GlobalLoaderFieldOverlappedError`: duplicated params between `global_loader_params` and `loader_params`
- `MissingCollector`: the collector cannot be found; not defined on ancestor nodes
- `MissingAnnotationError`: type annotation is missing when using `AutoLoad` or other annotations that require type information

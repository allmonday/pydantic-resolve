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
        Relationship(field='user_id', target_kls=User, loader=user_loader)
    ]
```

**Parameters:**

- `field` (str): The foreign key field name
- `target_kls` (type): The target Pydantic model class
- `loader` (Callable): DataLoader function to fetch the target entity
- `field_fn` (Callable | None): Optional function to transform the FK value before passing to loader
- `field_none_default` (Any | None): Default value to return if FK is None
- `field_none_default_factory` (Callable | None): Factory function to create default value if FK is None
- `load_many` (bool): Whether to use `load_many` instead of `load` (for to-many relationships)
- `load_many_fn` (Callable | None): Optional function to manually split FK values for load_many

#### MultipleRelationship

Defines multiple relationships between two entities under the same field.

```python
from pydantic_resolve import MultipleRelationship, Link

class Comment(BaseModel):
    id: int
    user_id: int
    moderator_id: int

    # Define two relationships via user_id: author and moderator
    __relationships__ = [
        MultipleRelationship(
            field='user_id',
            target_kls=User,
            links=[
                Link(biz='author', loader=user_loader),
                Link(biz='moderator', loader=moderator_loader)
            ]
        )
    ]
```

**Parameters:**

- `field` (str): The foreign key field name
- `target_kls` (type): The target Pydantic model class
- `links` (list[Link]): List of Link objects defining different relationships

#### Link

Defines a single link in a MultipleRelationship.

**Parameters:**

- `biz` (str): Business identifier to distinguish multiple relationships
- `loader` (Callable): DataLoader function
- `field_fn` (Callable | None): Optional function to transform FK value
- `field_none_default` (Any | None): Default value if FK is None
- `field_none_default_factory` (Callable | None): Factory for default value
- `load_many` (bool): Whether to use load_many
- `load_many_fn` (Callable | None): Manual split function for load_many
- `field_name` (str | None): Specifies that the loader returns a field value from the target class, not the full object. Must be used with `LoadBy(origin_kls=...)` to indicate the original object type.

Example: If `field_name="name"`, the loader returns `list[str]` (name field values) instead of `list[Foo]` (full objects). This is useful when you only need specific field values and want to avoid loading full objects.

#### Entity

Defines entity metadata including its relationships.

```python
from pydantic_resolve import Entity

Entity(
    kls=Comment,
    relationships=[
        Relationship(field='user_id', target_kls=User, loader=user_loader)
    ]
)
```

**Parameters:**

- `kls` (type[BaseModel]): The Pydantic model class
- `relationships` (list[Relationship | MultipleRelationship]): List of relationships

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
        Relationship(field='org_id', target_kls=Organization, loader=org_loader)
    ]

class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int

    __relationships__ = [
        Relationship(field='user_id', target_kls=User, loader=user_loader)
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
           Relationship(field='user_id', target_kls='User', loader=user_loader)
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
               field='user_id',
               target_kls='app.models.user:User',  # module.path:ClassName
               loader=user_loader
           )
       ]
   ```

The `_resolve_ref` function supports:

- Simple class names: `'User'` (looked up in the current module)
- Module path syntax: `'app.models.user:User'` (lazy import from any module)
- List generics: `list['User']` or `list['app.models.user:User']`

#### LoadBy

1. Annotation to automatically resolve fields based on ERD relationships.

```python
from pydantic_resolve import LoadBy, base_entity, config_global_resolver

# 1. Define entities with BaseEntity
BaseEntity = base_entity()

class User(BaseModel, BaseEntity):
    id: int
    name: str
    __relationships__ = [
        Relationship(field='org_id', target_kls=Organization, loader=org_loader)
    ]
```

2. Register ERD globally

```python
config_global_resolver(BaseEntity.get_diagram())
```

3. Use LoadBy in response models

```python
class UserResponse(BaseModel):
    id: int
    name: str

    # Automatically resolves via ERD relationship
    organization: Annotated[Optional[Organization], LoadBy('org_id')] = None
```

**Parameters:**

- `key` (str): The foreign key field name
- `biz` (str | None): Business identifier for MultipleRelationship
- `origin_kls` (type | None): Must be provided when the Link's `field_name` is set. Indicates the original object type before field extraction.

**Note:** `LoadBy` works with `config_global_resolver()` to inject the ERD into the default Resolver.

#### Using field_name with origin_kls

When a loader returns field values instead of full objects, use `field_name` in Link and `origin_kls` in LoadBy:

```python
from typing import Annotated

# DataLoader that returns list[str] (name values) instead of list[Foo] (full objects)
class FooNameLoader(DataLoader):
    async def batch_load_fn(self, keys):
        # Returns: [["foo1", "foo2"], ["foo3"]]
        return [[vv['name'] for vv in v] for v in load_foo_names(keys)]

class Biz(BaseModel, BaseEntity):
    __relationships__ = [
        MultipleRelationship(
            field='id',
            target_kls=list[Foo],  # Original type is list[Foo]
            links=[
                Link(biz='foo_name', field_name="name", loader=FooNameLoader)  # But loader returns list[str] (name field)
            ]
        )
    ]

class BizResponse(BaseModel):
    # origin_kls tells the system the relationship is originally list[Foo]
    # even though the loader actually returns list[str]
    foo_names: Annotated[List[str], LoadBy('id', biz='foo_name', origin_kls=list[Foo])] = []
```

This allows the system to:
- Correctly validate types (`list[str]` is compatible with `list[Foo].name`)
- Generate proper API documentation
- Provide type hints for fastapi-voyager

#### config_resolver()

Creates a new Resolver class with specific ERD configuration.

```python
from pydantic_resolve import config_resolver, ErDiagram, Entity

diagram = ErDiagram(configs=[...])
CustomResolver = config_resolver(diagram)

result = await CustomResolver().resolve(data)
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

### Handling None FK Values

When a foreign key is None, you can specify what to return:

```python
Relationship(
    field='user_id',
    target_kls=User,
    loader=user_loader,
    field_none_default=None,  # or
    field_none_default_factory=lambda: AnonymousUser()
)
```

When using `load_many`:

```python
Relationship(
    field='tag_ids',
    target_kls=Tag,
    loader=tag_loader,
    load_many=True,
    load_many_fn=lambda ids: ids.split(',') if ids else []  # Handle comma-separated values
)
```

### Multiple Relationships

When one field can mean different things, use `MultipleRelationship`:

```python
class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int  # Can be author OR moderator

    __relationships__ = [
        MultipleRelationship(
            field='user_id',
            target_kls=User,
            links=[
                Link(biz='author', loader=user_loader),
                Link(biz='moderator', loader=moderator_loader)
            ]
        )
    ]

class CommentResponse(BaseModel):
    id: int

    # Specify which relationship to use via the 'biz' parameter
    author: Annotated[Optional[User], LoadBy('user_id', biz='author')] = None
    moderator: Annotated[Optional[User], LoadBy('user_id', biz='moderator')] = None
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
from pydantic_resolve import ExposeAs, SendTo, LoadBy

class Comment(BaseModel):
    owner: Annotated[
        Optional[User],
        LoadBy('user_id'),      # Auto-resolve via ERD
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

## Helper Utilities

### build_list, build_object

Used in a DataLoader to group fetched records by `keys`.

`build_list` returns a list of objects; `build_object` returns a single object.

Signature: `build_list(data, keys, lambda d: d.key)`

### model_config

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

## Exceptions

- `ResolverTargetAttrNotFound`: target field does not exist
- `LoaderFieldNotProvidedError`: required Loader parameters are not provided in `resolve`
- `GlobalLoaderFieldOverlappedError`: duplicated params between `global_loader_params` and `loader_params`
- `MissingCollector`: the collector cannot be found; not defined on ancestor nodes
- `MissingAnnotationError`: type annotation is missing when using `LoadBy` or other annotations that require type information

# GraphQL Implementation - Feature Comparison

This document compares the auto-generated GraphQL implementation in pydantic-resolve with standard GraphQL features.

## Overview

The `pydantic_resolve/graphql/` module implements a GraphQL server that auto-generates schemas from Entity definitions and executes queries using pydantic-resolve's ERD system.

---

## Feature Comparison Table

### Core Operations

| Feature | Standard GraphQL | pydantic-resolve GraphQL | Status |
|---------|-----------------|-------------------------|--------|
| **Queries** | Full support | ✅ Supported | Full |
| **Mutations** | Full support | ✅ Supported | Full |
| **Subscriptions** | Real-time via WebSocket/SSE | ❌ Not supported | Missing |
| **Introspection** | `__schema`, `__type` | ✅ Supported | Full |

### Query Features

| Feature | Standard GraphQL | pydantic-resolve GraphQL | Status |
|---------|-----------------|-------------------------|--------|
| **Field Selection** | Select specific fields | ✅ Supported | Full |
| **Aliases** | Field renaming | ✅ Supported | Full |
| **Arguments** | Field-level parameters | ✅ Supported | Full |
| **Nested Queries** | Multi-level relationships | ✅ Supported | Full |
| **Variables** | Reusable query values | ⚠️ Basic | Partial |
| **Fragments** | Reusable field sets | ❌ Not supported | Missing |
| **Inline Fragments** | Type-specific fields | ❌ Not supported | Missing |
| **Operation Name** | Named operations | ✅ Supported | Full |
| **Multiple Operations** | Query + Mutation in one request | ⚠️ Single operation only | Partial |

### Type System

| Feature | Standard GraphQL | pydantic-resolve GraphQL | Status |
|---------|-----------------|-------------------------|--------|
| **Scalar Types** | Int, Float, String, Boolean, ID | ✅ Supported | Full |
| **Object Types** | Complex types with fields | ✅ Supported | Full |
| **Input Types** | Complex input objects | ✅ Supported (via BaseModel) | Full |
| **Enum Types** | Enumeration values | ✅ Supported (Enum, IntEnum) | Full |
| **Union Types** | One of multiple types | ❌ Not supported | Missing |
| **Interface Types** | Shared field contracts | ❌ Not supported | Missing |
| **List Types** | `[Type]`, `[Type!]` | ✅ Supported | Full |
| **Non-Null Types** | `Type!` | ✅ Supported | Full |
| **Custom Scalars** | Date, DateTime, etc. | ⚠️ Limited to built-in | Partial |

### Directives

| Feature | Standard GraphQL | pydantic-resolve GraphQL | Status |
|---------|-----------------|-------------------------|--------|
| **@skip** | Conditional skip | ❌ Not supported | Missing |
| **@include** | Conditional include | ❌ Not supported | Missing |
| **@deprecated** | Field deprecation | ❌ Not supported | Missing |
| **Custom Directives** | User-defined directives | ❌ Not supported | Missing |

### Advanced Features

| Feature | Standard GraphQL | pydantic-resolve GraphQL | Status |
|---------|-----------------|-------------------------|--------|
| **DataLoader/Batching** | Manual setup required | ✅ Built-in via ERD | Advantage |
| **N+1 Prevention** | Manual DataLoader | ✅ Automatic | Advantage |
| **Type Safety** | Schema-first | ✅ Pydantic-native | Advantage |
| **Federation** | Apollo Federation | ❌ Not supported | Missing |
| **Live Queries** | Real-time updates | ❌ Not supported | Missing |
| **Deferred Queries** | `@defer` directive | ❌ Not supported | Missing |
| **Stream Queries** | `@stream` directive | ❌ Not supported | Missing |

---

## Supported Features (Detailed)

### ✅ Queries
- Defined via `@query` decorator on Entity classes
- Support for arguments with type conversion
- Nested field resolution via ERD relationships
- Concurrent execution of multiple query fields
- Automatic DataLoader integration

### ✅ Mutations
- Defined via `@mutation` decorator on Entity classes
- Sequential execution (preserves order)
- Input types via Pydantic BaseModel parameters
- Return types with full resolution

### ✅ Introspection
- Full `__schema` query support
- Full `__type` query support
- GraphiQL IDE compatibility
- Field and argument introspection
- Type discovery

### ✅ Type System
- Scalar types: Int, Float, String, Boolean, ID
- Object types from Entity classes
- Input types from Pydantic BaseModel
- List and Non-null modifiers
- Automatic type mapping

### ✅ Query Parsing
- Field selection with proper aliasing
- Argument extraction with type conversion
- Nested field traversal
- Multiple root fields

### ✅ Performance Optimizations
- LRU caching for ResponseBuilder (256 entries)
- Concurrent query execution with asyncio.gather
- Automatic DataLoader batching via ERD
- Selective field loading optimization

---

## Partially Supported Features

### ⚠️ Variables
- **What works**: Basic variable extraction from operation definition
- **What's missing**:
  - Variable validation against input types
  - Default values for variables
  - `$variable` syntax in query execution

### ⚠️ Custom Scalars
- **What works**: Built-in Python type → GraphQL scalar mapping
- **What's missing**:
  - Custom scalar definition (Date, DateTime, JSON, etc.)
  - Scalar validation logic
  - Custom serialization/deserialization

### ⚠️ Multiple Operations
- **What works**: Single named operation support
- **What's missing**:
  - Multiple operations in single request
  - Operation selection by `operationName`

---

## Not Supported Features (Missing)

### ❌ Subscriptions
Real-time data via WebSocket or Server-Sent Events not implemented.

**Impact**: Cannot push real-time updates to clients.

**Workaround**: Polling via queries.

### ❌ Fragments
Reusable field sets not supported.

```graphql
# NOT SUPPORTED
fragment userFields on User {
  id
  name
  email
}

query {
  users {
    ...userFields
  }
}
```

**Impact**: Query duplication for repeated field patterns.

### ❌ Inline Fragments
Type-specific fields not supported.

```graphql
# NOT SUPPORTED
query {
  search {
    ... on User {
      email
    }
    ... on Post {
      title
    }
  }
}
```

**Impact**: Cannot query interface/union types with type-specific fields.

### ❌ Directives
`@skip`, `@include`, `@deprecated` not supported.

```graphql
# NOT SUPPORTED
query {
  user(id: 1) {
    name
    email @skip(if: $skipEmail)
  }
}
```

**Impact**: No conditional field inclusion at query time.

### ✅ Enum Types
Python Enum types are fully supported in entities and responses.

```python
from enum import Enum

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class UserEntity(BaseModel, BaseEntity):
    id: int
    status: Status
```

Generated GraphQL schema:
```graphql
enum Status {
  ACTIVE
  INACTIVE
}

type UserEntity {
  id: Int!
  status: Status!
}
```

**Features**:
- Support for standard `Enum` (string values)
- Support for `IntEnum` (integer values)
- Automatic enum type generation in SDL
- Introspection support for enum types
- Values serialized as enum values (not enum objects)

### ❌ Union Types
Union types not supported.

```graphql
# NOT SUPPORTED
union SearchResult = User | Post
```

**Impact**: Cannot return one of multiple possible types.

### ❌ Interface Types
Interface types not supported.

```graphql
# NOT SUPPORTED
interface Node {
  id: ID!
}

type User implements Node {
  id: ID!
  name: String!
}
```

**Impact**: No shared field contracts across types.

### ❌ Apollo Federation
Federation 1.x/2.x not supported.

**Impact**: Cannot use as subgraph in federated schema.

---

## Unique Advantages

### 🚀 Built-in DataLoader
pydantic-resolve GraphQL automatically batches database queries through the ERD system.

**Standard GraphQL**:
```python
# Manual DataLoader setup required
from graphene import DataLoader

async def load_users(ids):
    return await fetch_users(ids)

user_loader = DataLoader(load_users)
```

**pydantic-resolve GraphQL**:
```python
# Automatic via ERD
class UserEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='id', target_kls=list[Post], loader=post_loader)
    ]
    # Batching happens automatically
```

### 🚀 Pydantic-native Type Safety
Types are defined once as Pydantic models, reused everywhere.

**Standard GraphQL**:
- Define types in GraphQL SDL
- Define types again in Python (code generation or manual)

**pydantic-resolve GraphQL**:
- Define once as Pydantic Entity
- Schema auto-generated
- Full type safety throughout

---

## Architecture Files

| File | Purpose |
|------|---------|
| `handler.py` | Central coordinator for GraphQL operations |
| `executor.py` | Two-phase query/mutation execution |
| `query_parser.py` | GraphQL query parsing using graphql-core |
| `response_builder.py` | Dynamic Pydantic model generation |
| `decorator.py` | `@query` and `@mutation` decorators |
| `schema_builder.py` | SDL schema generation |
| `introspection.py` | Introspection query handling |
| `type_mapping.py` | Python → GraphQL type conversion |
| `exceptions.py` | GraphQL error handling |
| `types.py` | GraphQL data structures |
| `schema/` | Unified schema generation components |

---

## Recommendations

### High Priority
1. **Variables**: Complete variable support with validation
2. **Fragments**: Add fragment support for query reusability
3. **Enum Types**: Add enum support for type-safe constants

### Medium Priority
4. **Directives**: Implement `@skip` and `@include`
5. **Custom Scalars**: Support Date, DateTime, JSON scalars
6. **Multiple Operations**: Allow multiple operations with `operationName` selection

### Low Priority
7. **Subscriptions**: Add WebSocket/SSE subscription support
8. **Union/Interface Types**: For complex type hierarchies
9. **Federation**: For microservice architectures

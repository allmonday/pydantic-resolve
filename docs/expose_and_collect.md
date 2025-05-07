# Expose and Collect

This set of advanced features provided by pydantic-resolve aims to solve the problem of data transmission and assembly across multiple layers, facilitating computations in scenarios with deeply nested structures.

## Providing Data to All Descendant Nodes

The `Company` type has three layers. Add an `introduction` field to the `Employee` type, containing `company - department - employee name`.

```python hl_lines="2 9 21 22"
class Company(BaseModel):
    __pydantic_resolve_expose__ = { 'name': 'company_name' }
    id: int
    name: str
    departments: List[Department]


class Department(BaseModel):
    __pydantic_resolve_expose__ = { 'name': 'department_name' }
    id: int
    name: str
    employees: List[Employee]


class Employee(BaseModel):
    id: int
    name: str

    introduction: str = ''
    def resolve_introduction(self, ancestor_context):
        company = ancestor_context['company_name']
        department = ancestor_context['department_name']
        return f'{company}/{department}/{self.name}'

```

`__pydantic_resolve_expose__` will convert the key in the definition to the value (alias) and then provide it to all descendant nodes.

The `name` in `Company` is converted to `company_name`, and descendant nodes get the data from `ancestor_context['company_name']`.

Note that the alias should be globally unique within the entire structure.

## Collecting Data from Descendant Nodes

Now suppose there is a `Report` class that has a `company` data, and then uses `complyees` to collect all `Employee`'s `introduction` fields.

```python hl_lines="7 26"
from pydantic_resolve import Collect

class Report(BaseModel):
    companies: List[Company]

    employees: List[str] = []
    def post_employees(self, collector=Collector('reporter')):
        return collector.values()


class Company(BaseModel):
    __pydantic_resolve_expose__ = { 'name': 'company_name' }
    id: int
    name: str
    departments: List[Department]


class Department(BaseModel):
    __pydantic_resolve_expose__ = { 'name': 'department_name' }
    id: int
    name: str
    employees: List[Employee]


class Employee(BaseModel):
    __pydantic_resolve_collect__ = {'introduction': 'reporter'}
    id: int
    name: str

    introduction: str = ''
    def resolve_introduction(self, ancestor_context):
        company = ancestor_context['company_name']
        department = ancestor_context['department_name']
        return f'{company}/{department}/{self.name}'
```

`__pydantic_resolve_collect__ = {'introduction': 'reporter'}` means that the value of the `introduction` field will be sent to the `reporter` collector at the end of the node's lifecycle.

Note that the collector needs to be defined in the post method because it must wait for all descendant nodes to complete their calculations before collecting data.

```python
    employees: List[str] = []
    def post_employees(self, collector=Collector('reporter')):
        return collector.values()
```

Like DataLoader, the collector parameter names and quantities are not limited.

```python
    employees: List[str] = []
    def post_employees(self, xxx=Collector('xxx'), yyy=Collector('yyy')):
        return xxx.values() + yyy.values()
```

Unlike the global uniqueness requirement for aliases in Expose, the collector's name can be defined at multiple levels. The same name collector can collect data of different scales based on the range of descendants.

For example, `Company` can also define `employees` and use the same name collector as in `Report` to collect data at the `Company` level.

```python hl_lines="7 18"
from pydantic_resolve import Collect

class Report(BaseModel):
    companies: List[Company]

    employees: List[str] = []
    def post_employees(self, collector=Collector('reporter')):
        return collector.values()


class Company(BaseModel):
    __pydantic_resolve_expose__ = { 'name': 'company_name' }
    id: int
    name: str
    departments: List[Department]

    employees: List[str] = []
    def post_employees(self, collector=Collector('reporter')):
        return collector.values()

class Department(BaseModel):
    __pydantic_resolve_expose__ = { 'name': 'department_name' }
    id: int
    name: str
    employees: List[Employee]


class Employee(BaseModel):
    __pydantic_resolve_collect__ = {'introduction': 'reporter'}
    id: int
    name: str

    introduction: str = ''
    def resolve_introduction(self, ancestor_context):
        company = ancestor_context['company_name']
        department = ancestor_context['department_name']
        return f'{company}/{department}/{self.name}'
```

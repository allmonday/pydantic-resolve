# 提供和收集 (expose and collect)

这是 pydantic-resolve 提供的一组高级功能。 它要解决的问题是跨多层的数据传递和组装问题，为一些层级较多的场景的计算提供便利。

## 向所有子孙节点提供数据

Company 类型的数据有三层， 现在要在 Employee 类中添加 introduction 字段， 内容为 company - department - employee name。

对于这种只向子集子孙节点提供数据的需求， 我们可以使用 Expose 来实现。

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

`__pydantic_resolve_expose__` 会将定义中的 key 转变为 value (别名)， 然后提供给所有子孙节点。

Company 中的 name 被转换为 `company_name`， 子孙节点从 `ancestor_context['company_name']` 获取数据。

需要注意别名应该是在整个结构中全局唯一的。

## 从子孙节点收集数据

现在假设有个 Resport 类， 它拥有一个 company 数据， 然后用 complyees 收集所有 Employee 的 introduction 字段

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

`__pydantic_resolve_collect__ = {'introduction': 'reporter'}` 的意思是将 introduction 字段的值， 在该节点的声明周期结束时， 发送给 `reporter` 收集者。

注意 collector 需要定义在 post 方法中， 因为必须等待子孙节点的运算都完成之后才可以收集数据。

```python
    employees: List[str] = []
    def post_employees(self, collector=Collector('reporter')):
        return collector.values()
```

和 DataLoader 一样， collecotr 参数名字和数量没有限制。

```python
    employees: List[str] = []
    def post_employees(self, xxx=Collector('xxx'), yyy=Collector('yyy')):
        return xxx.values() + yyy.values()
```

和 Expose 中限制别名全局唯一不同， collector 的名字可以定义在多层之中。 代表的含义相同名字的收集者可以根据子孙范围收集到不同规模的数据。

比如 Company 中也能定义 employees，使用和 Report 中相同名字的收集器来收集 Company 级别的数据。

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

使用收集器可以非常简单的跨层收集数据。
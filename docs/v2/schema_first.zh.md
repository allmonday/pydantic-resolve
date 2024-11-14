# 先定义模型，再添加过程

使用 pydantic-resolve 的思考方式是先定义模型。

当我们构建数据时， 一个很朴素的思考方式是：先理清所需的数据格式 Target， 比较当前所拥有的数据源格式 Source ，寻找最短的变化路径。

举个例子我想获取每个人的请假信息， 包含年假，病假两种数据。 那么期望的数据结构将是:

```python
class Person(BaseModel):
    id: int
    name: str
    absenses: List[Absense]

class Absense(BaseModel):
    type: Literal['annual', 'sick']
    start_date: date
    end_date: date
```

而手头已有的数据为:

```python
class AnnualLeave(BaseModel):
    person_id: int
    start_date: date
    end_date: date

class SickLeave(BaseModel):
    person_id: int
    start_date: date
    end_date: date
```

那么此时我们可以把源数据和期望数据组合在一起, 定义好需要获取的数据和将要计算出来的结果。 配合 `exclude=True` 把临时变量在最终输出中隐藏。

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str
    absenses: List[Absense] = []

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
```

然后我们为 `annual_leaves` 和 `sick_leaves` 添加 resolve 和 dataloader 来获取数据：

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str
    absense: List[Absense] = []

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    def resolve_annual_leaves(self, loader=LoaderDepend(AnnualLeaveLoader)):
        return loader.load(self.id)

    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
    def resolve_sick_leaves(self, loader=LoaderDepend(SickLeaveLoader)):
        return loader.load(self.id)
```

接着当 `annual_leaves` 和 `sick_leaves` 在 resolve 阶段结束， 获取了数据之后， 利用 post 阶段来计算 absenses

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str
    absenses: List[Absense] = []
    def post_absense(self):
        a = [Absense(type='annual', start_date=a.start_date, end_date=a.end_date) for a in self.annual_leaves]
        b = [Absense(type='annual', start_date=s.start_date, end_date=s.end_date) for a in self.sick_leaves]
        return a + b

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    def resolve_annual_leaves(self, loader=LoaderDepend(AnnualLeaveLoader)):
        return loader.load(self.id)

    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
    def resolve_sick_leaves(self, loader=LoaderDepend(SickLeaveLoader)):
        return loader.load(self.id)
```

当定义完整个 Person, Absense 的结构后， 我们就能通过初始化 persons 来加载和计算所有数据了，只需对 persons 数据执行一次 Resolver().resolve() 就能完成所有的操作。

```python
persons = [Person(id=1, name='alice'), Person(id=2, name='bob')]
persons = await Resolver().resolve(persons)
```

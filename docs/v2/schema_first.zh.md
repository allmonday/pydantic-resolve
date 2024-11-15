# 先定义模型，再添加过程

使用 pydantic-resolve 的推荐方式是先定义模型。 将所有的操作都附加在定义好的数据对象上。

当我们构建数据时， 一个很朴素的思考方式是：先定义好目标数据结构 Target， 比较当前已有的数据源结构 Source ，寻找最短的变化路径。

比如我有一个 Person 的数组， 现在要为每个人增加请假信息， 原始请假数据包含年假，病假两种， 要把两者合并成一个类型。 期望的数据结构就是:

## 期望的结构

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

## 添加数据源

假设已有的数据是两个 Leave 类型以及他们根据 person_id 获取数据的 dataloader （省略）

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

那么此时我们可以把源数据和期望数据组合在一起, 定义好需要获取的数据和将要计算出来的结果。

配合 `exclude=True` 可以在最终输出中隐藏临时变量。

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)

    absenses: List[Absense] = []
```

## 加载数据

然后我们为 `annual_leaves` 和 `sick_leaves` 添加 resolve 和 dataloader 来获取数据：

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    def resolve_annual_leaves(self, loader=LoaderDepend(AnnualLeaveLoader)):
        return loader.load(self.id)

    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
    def resolve_sick_leaves(self, loader=LoaderDepend(SickLeaveLoader)):
        return loader.load(self.id)

    absense: List[Absense] = []
```

## 转换数据

最后， 当 `annual_leaves` 和 `sick_leaves` 在 resolve 阶段结束， 获取了数据之后， 利用 post 阶段来计算 absenses

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    def resolve_annual_leaves(self, loader=LoaderDepend(AnnualLeaveLoader)):
        return loader.load(self.id)

    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
    def resolve_sick_leaves(self, loader=LoaderDepend(SickLeaveLoader)):
        return loader.load(self.id)

    absenses: List[Absense] = []
    def post_absense(self):
        a = [Absense(
                type='annual',
                start_date=a.start_date,
                end_date=a.end_date) for a in self.annual_leaves]
        b = [Absense(
                type='sick',
                start_date=s.start_date,
                end_date=s.end_date) for a in self.sick_leaves]
        return a + b
```

当定义完整个 Person, Absense 的结构后， 我们就能通过初始化 people 来加载和计算所有数据了，只需对 people 数据执行一次 Resolver().resolve() 就能完成所有的操作。

```python
people = [Person(id=1, name='alice'), Person(id=2, name='bob')]
people = await Resolver().resolve(people)
```

在这整个拼装过程中， 我们没有书写一行循环展开 people 的代码，所有的相关代码都在 Person 对象的内部。

如果使用面向过程的方式来处理的话， 会需要至少考虑：

- annual, sick leaves 根据 person_id 聚合，生成 person_annual_map 和 person_sick_map 两个新变量
- `for person in people` 遍历 person 对象

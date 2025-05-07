# 继承和复用

如果一个 query 方法， 或者 DataLoader 可以返回类型 Car 的数据， 那么继承了 Car 的子类 CarWithRepairHistories， 可以在任意场景直接替换 Car

在 resolve 之后, CarWithRepairHistories 下的数据就会被加载进去

> 前提是子类扩展的字段都有默认值。

比如：

```python
class Car(BaseModel):
    id: int
    name: str

def query_car():
    return dict(id=1, name='Ford')

class ReturnData(BaseModel):
    car: Optional[Car] = None
    def resolve_car(self):
        return query_car()
```

就可以用 CarWithRepairHistories 直接替换 Car， 而无需修改 `query_car` 等查询方法。

```python
class Car(BaseModel):
    id: int
    name: str

def query_car():
    return dict(id=1, name='Ford')

class CarWithRepairHistories(A):
    histories: List[RepairHistory] = []  # 默认值
    def resolve_histories(self, loader=LoaderDepend(RepairHistoriesLoader)):
        return loader.load(self.id)

class ReturnData(BaseModel):
    # car: Optional[Car] = None
    car: Optional[CarWithRepairHistories] = None
    def resolve_car(self):
        return query_a()  # 无需调整
```

因此获取数据的方法,或者 DataLoader 都能被复用, 为各种子类提供数据.

子类继承能够复用父类的字段, 减少重复定义字段的开销. 

利用好继承我们就能为 "面向 ERD 开发" 这个高效的开发模式做好铺垫.
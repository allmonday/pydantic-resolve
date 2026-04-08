# Inheritance and Reuse

If a query method or DataLoader can return data of type `Car`, then a subclass `CarWithRepairHistories` that inherits from `Car` can directly replace `Car` in any scenario.

After resolving, the data under `CarWithRepairHistories` will be loaded.

> The prerequisite is that the fields extended by the subclass all have default values.

For example:

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

You can directly replace `Car` with `CarWithRepairHistories` without modifying `query_car` and other query methods.

```python
class Car(BaseModel):
    id: int
    name: str

def query_car():
    return dict(id=1, name='Ford')

class CarWithRepairHistories(A):
    histories: List[RepairHistory] = []  # Default value
    def resolve_histories(self, loader=LoaderDepend(RepairHistoriesLoader)):
        return loader.load(self.id)

class ReturnData(BaseModel):
    # car: Optional[Car] = None
    car: Optional[CarWithRepairHistories] = None
    def resolve_car(self):
        return query_a()  # No adjustment needed
```

Therefore, the methods for obtaining data or DataLoader can be reused to provide data for various subclasses.

Subclass inheritance can reuse the fields of the parent class, reducing the overhead of repeatedly defining fields.

Of course, using meta class `DefineSubset` can also works.
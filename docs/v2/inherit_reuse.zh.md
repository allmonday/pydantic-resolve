# 继承和复用

如果一个 query 方法， 或者 DataLoader 可以返回类型 A 的数据， 那么继承了 A 的子类 B， 可以直接替换 A， 前提是 B 扩展的字段都有默认值。

比如：

```python
class A(BaseModel):
    name: str

def query_a():
    return dict(name='a1')

class ReturnData(BaseModel):
    a: Optional[A] = None
    def resolve_a(self):
        return query_a()
```

就能用 B 直接替换 A， 而无需修改 `query_a` 等查询方法。

```python
class A(BaseModel):
    name: str

class B(A):
    new_field: str = ''
    new_items: List[Item] = []

class ReturnData(BaseModel):
    a: Optional[B] = None
    def resolve_a(self):
        return query_a()  # 无需调整
```

# Pydantic-Resolve Benchmark Suite

这套基准测试用于衡量 pydantic-resolve 在各种常见使用场景下的性能表现，为性能优化提供基准数据。

## 📋 目录

- [快速开始](#快速开始)
- [Benchmark 概览](#benchmark-概览)
- [运行测试](#运行测试)
- [性能基准](#性能基准)
- [常用用法归纳](#常用用法归纳)

## 🚀 快速开始

### 运行所有 Benchmark

```bash
# 运行所有基准测试
pytest benchmarks/test_benchmark.py -v

# 运行并显示详细时间
pytest benchmarks/test_benchmark.py --durations=0

# 运行并生成汇总报告
pytest benchmarks/test_benchmark.py::test_benchmark_summary -v
```

### 运行单个 Benchmark

```bash
# 测试基础解析性能
pytest benchmarks/test_benchmark.py::test_benchmark_basic_resolve -v

# 测试 DataLoader 批量加载
pytest benchmarks/test_benchmark.py::test_benchmark_dataloader_batch -v

# 测试真实场景
pytest benchmarks/test_benchmark.py::test_benchmark_real_world_ecommerce -v
```

### 按模式运行

```bash
# 运行所有标记为 benchmark 的测试
pytest benchmarks/test_benchmark.py -m benchmark

# 运行特定名称的测试
pytest benchmarks/test_benchmark.py -k dataloader -v
pytest benchmarks/test_benchmark.py -k "er_diagram or mapper" -v
```

## 📊 Benchmark 概览

| # | Benchmark | 场景 | 数据规模 | 预期时间 | 测试内容 |
|---|-----------|------|----------|----------|----------|
| 1 | Basic Resolve | 基础解析 | 100 students | < 0.5s | 同步/异步 resolve 方法 |
| 2 | DataLoader | 批量加载 | 1000 tasks, 10 users | < 0.5s | N+1 查询优化 |
| 3 | Post Methods | 后处理 | 100 orders | < 0.3s | 派生字段计算 |
| 4 | Collector | 收集器 | 50 blogs, 500 posts | < 1s | 子节点向父节点收集数据 |
| 5 | Expose | 暴露器 | 20 roots, 1000 nodes | < 1s | 父节点向子节点暴露数据 |
| 6 | Mapper | 映射器 | 100 students, 2000 courses | < 1s | 数据转换 |
| 7 | ER Diagram | 关系图 | 200 users, 3-level depth | < 1.5s | 自动 resolve 生成 |
| 8 | Deep Nesting | 深度嵌套 | 364 nodes, depth 5 | < 1s | 递归遍历效率 |
| 9 | Large Dataset | 大数据集 | 1000 products, 4000 total | < 2s | 可扩展性 |
| 10 | E-commerce | 真实场景 | 10 stores, 500 orders | < 3s | 综合性能测试 |

## 🎯 性能基准

基于以下环境测试：
- Python 3.10+
- Pydantic v2
- MacBook Pro M1 (或类似硬件)

### 预期性能指标

```
Basic Resolve:        100 nodes   ~ 50-200ms
DataLoader Batch:     1000 tasks  ~ 100-300ms
Post Methods:         100 orders  ~ 50-150ms
Collector Pattern:    500 posts   ~ 200-500ms
Expose Pattern:       1000 nodes  ~ 200-600ms
Mapper:               2000 items  ~ 300-800ms
ER Diagram:           200 users   ~ 500-1200ms
Deep Nesting:         364 nodes   ~ 300-700ms
Large Dataset:        4000 objs   ~ 800-1500ms
E-commerce:           5250 objs   ~ 1500-2500ms
```

> ⚠️ **注意**: 实际性能取决于硬件、操作系统、Python 版本等因素。

## 📖 常用用法归纳

基于对 92 个测试文件的分析，归纳出以下常用用法：

### 1. 基础 Resolve 方法 (Basic Resolve)

**最常用的模式**，用于填充字段数据。

```python
class Student(BaseModel):
    name: str

    # 同步 resolve
    display_name: str = ''
    def resolve_display_name(self) -> str:
        return f'Student: {self.name}'

    # 异步 resolve
    courses: List[str] = []
    async def resolve_courses(self) -> List[str]:
        return await fetch_courses(self.id)
```

**使用场景**:
- 从数据库加载关联数据
- 调用 API 获取额外信息
- 计算派生字段

---

### 2. DataLoader 批量加载 (Batch Loading)

**核心特性**，避免 N+1 查询问题。

```python
class UserLoader(DataLoader):
    async def batch_load_fn(self, keys: List[int]):
        # 一次查询加载所有用户
        users = await db.query(User).where(User.id.in_(keys)).all()
        user_map = {u.id: u for u in users}
        return [user_map.get(k) for k in keys]

class Task(BaseModel):
    user_id: int
    owner: Optional[User] = None
    async def resolve_owner(self, loader=LoaderDepend(UserLoader)):
        return await loader.load(self.user_id)
```

**使用场景**:
- 加载关联对象 (用户、产品等)
- 批量 API 调用
- 数据库关联查询优化

---

### 3. Post 方法 (Post-Method)

**常用模式**，用于在所有 resolve 完成后计算派生字段。

```python
class Order(BaseModel):
    items: List[OrderItem] = []
    async def resolve_items(self):
        return await fetch_items(self.id)

    total: float = 0
    def post_total(self):
        return sum(item.price for item in self.items)

    item_count: int = 0
    def post_item_count(self):
        return len(self.items)
```

**使用场景**:
- 计算总和、平均值
- 统计数量
- 格式化数据
- 条件判断

---

### 4. Collector 模式 (Collector)

**高级特性**，从子节点向父节点收集数据。

```python
class Post(BaseModel):
    __pydantic_resolve_collect__ = {
        'comment_count': 'post_comments'
    }
    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)

class Blog(BaseModel):
    posts: List[Post] = []

    total_comments: int = 0
    def post_total_comments(self, collector=Collector('post_comments', flat=True)):
        return sum(collector.values())
```

**使用场景**:
- 汇总子节点数据
- 层级数据统计
- 深度聚合计算

---

### 5. Expose 模式 (Expose)

**高级特性**，从父节点向子节点暴露数据。

```python
class Root(BaseModel):
    __pydantic_resolve_expose__ = {
        'name': 'root_name'
    }
    name: str
    children: List[Child] = []

class Child(BaseModel):
    # 访问祖先节点的数据
    root_name: str = ''
    def post_root_name(self, ancestor_context):
        return ancestor_context.get('root_name')
```

**使用场景**:
- 上下文传递
- 配置传播
- 路径构建
- 权限验证

---

### 6. Mapper 转换 (Mapper)

**数据转换**，用于在不同数据模型间转换。

```python
class CourseDTO(BaseModel):
    """外部 API 格式"""
    id: int
    title: str

class Course(BaseModel):
    """内部格式"""
    id: int
    name: str

class Student(BaseModel):
    courses: List[Course] = []

    @mapper(lambda items: [Course(id=c.id, name=c.title) for c in items])
    async def resolve_courses(self) -> List[CourseDTO]:
        return await external_api.get_courses()
```

**使用场景**:
- API 响应转换
- DTO 到 Domain Model
- 数据清洗
- 格式统一

---

### 7. ER Diagram + LoadBy (自动生成)

**最高级用法**，声明式关系定义，自动生成 resolve 方法。

```python
BaseEntity = base_entity()

class UserEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='profile_id', target_kls=ProfileEntity, loader=ProfileLoader)
    ]
    id: int
    profile_id: int

diagram = BaseEntity.get_diagram()
config_global_resolver(diagram)

class UserResponse(BaseModel):
    id: int
    profile_id: int

    # 自动生成 resolve_profile 方法
    profile: Annotated[Optional[ProfileResponse], LoadBy('profile_id')] = None
```

**使用场景**:
- 大型项目
- 复杂关系模型
- 需要统一管理关系定义
- 配合 fastapi-voyager 可视化

---

### 8. 上下文参数 (Context, Parent, Ancestor)

**高级特性**，在 resolve/post 方法中访问上下文。

```python
class MyModel(BaseModel):
    # 访问用户传入的 context
    value: str = ''
    def resolve_value(self, context):
        return context.get('some_key')

    # 访问父节点
    parent_name: str = ''
    def post_parent_name(self, parent):
        return parent.name if parent else ''

    # 访问祖先节点
    root_id: int = 0
    def post_root_id(self, ancestor_context):
        return ancestor_context.get('root_id', 0)
```

**使用场景**:
- 传递用户信息
- 访问父节点数据
- 构建数据链路
- 多租户隔离

---

## 🔍 性能优化建议

基于 benchmark 结果，以下是一些性能优化建议：

### 1. 使用 DataLoader 批量加载

❌ **不推荐**:
```python
# N+1 查询问题
for task in tasks:
    task.owner = await get_user(task.user_id)  # N 次查询
```

✅ **推荐**:
```python
# 批量加载
class Task(BaseModel):
    owner: Optional[User] = None
    async def resolve_owner(self, loader=LoaderDepend(UserLoader)):
        return await loader.load(self.user_id)
```

### 2. 避免过度嵌套

❌ **不推荐**:
```python
# 10+ 层嵌套难以维护且性能差
class A:
    b: Optional[B]
class B:
    c: Optional[C]
# ...
```

✅ **推荐**:
```python
# 控制深度在 3-5 层
class A:
    b: Optional[B]
    # 如果 B 很复杂，考虑使用 DataLoader 延迟加载
```

### 3. 合理使用 Post 方法

❌ **不推荐**:
```python
# 在 post 中进行 I/O 操作
def post_total(self):
    return await fetch_total_from_api()  # 不要这样做！
```

✅ **推荐**:
```python
# post 只做计算，I/O 放在 resolve 中
total: float = 0
async def resolve_total(self):
    return await fetch_total_from_api()

# 或者
items: List[Item] = []
async def resolve_items(self):
    return await fetch_items()

def post_total(self):
    return sum(i.price for i in self.items)  # 纯计算
```

### 4. 缓存元数据

元数据扫描会消耗一定时间，建议启用缓存：

```python
# METADATA_CACHE 在 resolver.py 中自动启用
# 首次扫描后会缓存结果，后续调用更快
```

### 5. 使用 Include/Exclude 过滤

如果某些字段不需要解析，可以使用过滤：

```python
# 未来可能支持
result = await Resolver(
    include_fields=['user', 'profile'],
    exclude_fields=['logs']
).resolve(data)
```

---

## 📈 持续监控

建议在 CI/CD 中运行 benchmark：

```yaml
# .github/workflows/benchmark.yml
name: Benchmark

on: [push, pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run benchmarks
        run: |
          pytest benchmarks/test_benchmark.py --durations=0 > benchmark.txt
          cat benchmark.txt
```

---

## 🤝 贡献

如果你发现性能问题或有优化建议，欢迎：

1. 运行 benchmark 确认问题
2. 提供详细的性能数据
3. 提交 PR 或 Issue

---

## 📝 许可

MIT License

---

## 📚 相关资源

- [pydantic-resolve 文档](https://allmonday.github.io/pydantic-resolve/)
- [API 参考](https://allmonday.github.io/pydantic-resolve/api/)
- [示例项目](https://github.com/allmonday/composition-oriented-development-pattern)
- [fastapi-voyager 可视化](https://github.com/allmonday/fastapi-voyager)

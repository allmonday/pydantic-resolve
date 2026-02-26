"""
GraphQL Schema generator from ERD and @query decorated methods.
"""

import inspect
from typing import Dict, List, get_args, get_origin, get_type_hints
from pydantic import BaseModel

from ..utils.er_diagram import ErDiagram, Relationship
from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from .exceptions import FieldNameConflictError
from .type_mapping import map_scalar_type


class SchemaBuilder:
    """从 ERD 和 @query 装饰的方法生成 GraphQL Schema"""

    def __init__(self, er_diagram: ErDiagram, validate_conflicts: bool = True):
        """
        Args:
            er_diagram: 实体关系图
            validate_conflicts: 是否验证字段名冲突（默认 True）
        """
        self.er_diagram = er_diagram
        self.validate_conflicts = validate_conflicts

    def build_schema(self) -> str:
        """
        生成完整的 GraphQL Schema

        Returns:
            GraphQL Schema 字符串
        """
        # 运行时验证字段冲突（双重保障）
        if self.validate_conflicts:
            self._validate_all_entities()

        input_defs = []  # Input types
        type_defs = []   # Output types
        query_defs = []
        mutation_defs = []
        processed_types = set()  # 跟踪已处理的类型，避免重复
        processed_input_types = set()  # 跟踪已处理的 input 类型

        # 生成所有实体类型
        for entity_cfg in self.er_diagram.configs:
            type_def = self._build_type_definition(entity_cfg)
            type_defs.append(type_def)
            processed_types.add(entity_cfg.kls)

            # 提取该实体的 @query 方法
            query_methods = self._extract_query_methods(entity_cfg.kls)
            for method in query_methods:
                query_defs.append(self._build_query_def(method))

            # 提取该实体的 @mutation 方法
            mutation_methods = self._extract_mutation_methods(entity_cfg.kls)
            for method in mutation_methods:
                mutation_defs.append(self._build_mutation_def(method))

        # 收集并生成所有嵌套的 Pydantic 类型
        nested_types = self._collect_nested_pydantic_types(processed_types)
        for nested_type in nested_types:
            if nested_type not in processed_types:
                type_def = self._build_type_definition_for_class(nested_type)
                type_defs.append(type_def)
                processed_types.add(nested_type)

        # 收集并生成所有 Input Types（从方法参数）
        input_types = self._collect_input_types()
        for input_type in input_types:
            if input_type not in processed_input_types:
                input_def = self._build_input_definition(input_type)
                input_defs.append(input_def)
                processed_input_types.add(input_type)

        # 组装完整的 Schema：先 input，再 type
        schema_parts = []

        # Input types
        if input_defs:
            schema_parts.append("\n".join(input_defs))

        # Output types
        if type_defs:
            schema_parts.append("\n".join(type_defs))

        schema = "\n\n".join(schema_parts) + "\n\n"

        # Query type
        schema += "type Query {\n"
        if query_defs:
            schema += "\n".join(f"  {qd}" for qd in query_defs) + "\n"
        schema += "}\n\n"

        # 只有在有 mutation 时才生成 Mutation 类型
        if mutation_defs:
            schema += "type Mutation {\n"
            schema += "\n".join(f"  {md}" for md in mutation_defs) + "\n"
            schema += "}\n"

        return schema

    def _build_type_definition(self, entity_cfg) -> str:
        """为单个实体生成 GraphQL 类型定义"""
        fields = []

        # 获取实体的所有字段提示
        try:
            type_hints = get_type_hints(entity_cfg.kls)
        except Exception:
            type_hints = {}

        # 处理标量字段
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            # 映射 Python 类型到 GraphQL 类型
            gql_type = self._map_python_type_to_gql(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        # 处理关联关系（来自 __relationships__）
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                # 只有提供了 default_field_name 的关系才暴露给 GraphQL
                if not hasattr(rel, 'default_field_name') or not rel.default_field_name:
                    continue

                field_name = rel.default_field_name

                # 处理泛型类型（如 list[PostEntity]）
                target_kls = rel.target_kls
                origin = get_origin(target_kls)

                if origin is list:
                    # list[PostEntity] -> PostEntity
                    args = get_args(target_kls)
                    if args:
                        target_name = args[0].__name__
                    else:
                        continue  # 无法确定元素类型，跳过
                else:
                    target_name = target_kls.__name__

                if rel.load_many:
                    gql_type = f"[{target_name}]!"
                else:
                    gql_type = target_name
                fields.append(f"  {field_name}: {gql_type}")

        return f"type {entity_cfg.kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _extract_query_methods(self, entity: type) -> List[Dict]:
        """
        提取 Entity 上所有 @query 装饰的方法

        Returns:
            方法信息列表，每个元素包含:
            - name: GraphQL 查询名称
            - description: 查询描述
            - params: 参数列表
            - return_type: 返回类型
            - entity: 实体类
            - method: 方法对象
        """
        methods = []

        for name, method in entity.__dict__.items():
            # 处理 classmethod - 访问底层函数
            actual_method = method
            if isinstance(method, classmethod):
                actual_method = method.__func__

            # 检查是否有 @query 装饰器的标记
            if not hasattr(actual_method, '_pydantic_resolve_query'):
                continue

            # 获取方法签名
            try:
                sig = inspect.signature(actual_method)
            except Exception:
                continue

            params = []

            # 跳过 self/cls 参数
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                # 构建 GraphQL 参数定义
                try:
                    gql_type = self._map_python_type_to_gql(param.annotation)
                except Exception:
                    # 无法推断类型，使用 Any
                    gql_type = 'Any'

                # 检查是否为必需参数
                default = param.default
                is_required = default == inspect.Parameter.empty

                # 参数定义不使用 $ 前缀，且 gql_type 已包含 ! 后缀
                if is_required:
                    param_str = f"{param_name}: {gql_type}"
                else:
                    # 移除末尾的 ! 表示可选
                    param_str = f"{param_name}: {gql_type.rstrip('!')}"

                params.append({
                    'name': param_name,
                    'type': gql_type,
                    'required': is_required,
                    'default': default,
                    'definition': param_str
                })

            # 确定返回类型
            try:
                return_type = sig.return_annotation
                gql_return_type = self._map_return_type_to_gql(return_type)
            except Exception:
                # 无法推断返回类型
                gql_return_type = 'Any'

            # 确定 GraphQL 查询名称
            query_name = actual_method._pydantic_resolve_query_name
            if not query_name:
                # 默认: get_all → users, get_by_id → user
                query_name = self._convert_to_query_name(name)

            description = actual_method._pydantic_resolve_query_description or ""

            methods.append({
                'name': query_name,
                'description': description,
                'params': params,
                'return_type': gql_return_type,
                'entity': entity,
                'method': actual_method  # 保存实际可调用的函数（对于 classmethod 是 __func__）
            })

        return methods

    def _extract_mutation_methods(self, entity: type) -> List[Dict]:
        """
        提取 Entity 上所有 @mutation 装饰的方法

        Returns:
            方法信息列表，每个元素包含:
            - name: GraphQL mutation 名称
            - description: mutation 描述
            - params: 参数列表
            - return_type: 返回类型
            - entity: 实体类
            - method: 方法对象
        """
        methods = []

        for name, method in entity.__dict__.items():
            # 处理 classmethod - 访问底层函数
            actual_method = method
            if isinstance(method, classmethod):
                actual_method = method.__func__

            # 检查是否有 @mutation 装饰器的标记
            if not hasattr(actual_method, '_pydantic_resolve_mutation'):
                continue

            # 获取方法签名
            try:
                sig = inspect.signature(actual_method)
            except Exception:
                continue

            params = []

            # 跳过 self/cls 参数
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                # 构建 GraphQL 参数定义
                try:
                    gql_type = self._map_python_type_to_gql(param.annotation)
                except Exception:
                    # 无法推断类型，使用 Any
                    gql_type = 'Any'

                # 检查是否为必需参数
                default = param.default
                is_required = default == inspect.Parameter.empty

                # 参数定义不使用 $ 前缀，且 gql_type 已包含 ! 后缀
                if is_required:
                    param_str = f"{param_name}: {gql_type}"
                else:
                    # 移除末尾的 ! 表示可选
                    param_str = f"{param_name}: {gql_type.rstrip('!')}"

                params.append({
                    'name': param_name,
                    'type': gql_type,
                    'required': is_required,
                    'default': default,
                    'definition': param_str
                })

            # 确定返回类型
            try:
                return_type = sig.return_annotation
                gql_return_type = self._map_return_type_to_gql(return_type)
            except Exception:
                # 无法推断返回类型
                gql_return_type = 'Any'

            # 确定 GraphQL mutation 名称
            mutation_name = actual_method._pydantic_resolve_mutation_name
            if not mutation_name:
                # 默认: create_user -> createUser
                mutation_name = self._convert_to_mutation_name(name)

            description = actual_method._pydantic_resolve_mutation_description or ""

            methods.append({
                'name': mutation_name,
                'description': description,
                'params': params,
                'return_type': gql_return_type,
                'entity': entity,
                'method': actual_method  # 保存实际可调用的函数（对于 classmethod 是 __func__）
            })

        return methods

    def _build_query_def(self, method_info: Dict) -> str:
        """构建单个查询定义"""
        name = method_info['name']

        # 构建参数部分
        params_str = ""
        if method_info['params']:
            params = ", ".join(p['definition'] for p in method_info['params'])
            params_str = f"({params})"

        # 构建返回类型
        return_type = method_info['return_type']

        return f"{name}{params_str}: {return_type}"

    def _build_mutation_def(self, method_info: Dict) -> str:
        """构建单个 mutation 定义"""
        name = method_info['name']

        # 构建参数部分
        params_str = ""
        if method_info['params']:
            params = ", ".join(p['definition'] for p in method_info['params'])
            params_str = f"({params})"

        # 构建返回类型
        return_type = method_info['return_type']

        return f"{name}{params_str}: {return_type}"

    def _map_python_type_to_gql(self, python_type: type) -> str:
        """
        将 Python 类型映射到 GraphQL 类型

        Args:
            python_type: Python 类型

        Returns:
            GraphQL 类型字符串（如 "String!", "[Int]!"）
        """
        # 使用 get_core_types 处理所有包装类型（Optional, list, Annotated 等）
        core_types = get_core_types(python_type)
        if not core_types:
            return "String!"  # 默认为 String

        core_type = core_types[0]
        origin = get_origin(python_type)

        # 检查是否是 list[T]
        is_list = origin is list or (
            hasattr(python_type, '__origin__') and
            python_type.__origin__ is list
        )

        if is_list:
            # list[T] -> [T!]!
            inner_gql = self._map_python_type_to_gql(core_type)
            return f"[{inner_gql}]!"
        else:
            # T -> T!
            if safe_issubclass(core_type, BaseModel):
                return f"{core_type.__name__}!"
            else:
                # 标量类型
                scalar_name = map_scalar_type(core_type)
                return f"{scalar_name}!"

    def _map_return_type_to_gql(self, return_type: type) -> str:
        """映射返回类型到 GraphQL 类型"""
        # 使用 get_core_types 处理所有包装类型
        core_types = get_core_types(return_type)
        if not core_types:
            return self._map_python_type_to_gql(return_type)

        core_type = core_types[0]
        origin = get_origin(return_type)

        # 处理 List[X]
        if origin is list:
            inner_gql = self._map_python_type_to_gql(core_type)
            return f"[{inner_gql}]"

        # 默认处理
        return self._map_python_type_to_gql(return_type)

    def _convert_to_query_name(self, method_name: str) -> str:
        """
        将方法名转换为 GraphQL 查询名称

        Examples:
            get_all -> all
            get_by_id -> by_id
            fetch_users -> users
        """
        # 移除常见前缀
        for prefix in ['get_', 'fetch_', 'find_', 'query_']:
            if method_name.startswith(prefix):
                method_name = method_name[len(prefix):]
                break

        # 转换为 camelCase
        return method_name

    def _convert_to_mutation_name(self, method_name: str) -> str:
        """
        将方法名转换为 GraphQL mutation 名称

        Examples:
            create_user -> createUser
            update_user -> updateUser
            delete_post -> deletePost
            add_comment -> addComment
        """
        # 转换 snake_case 到 camelCase
        components = method_name.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])

    def _validate_all_entities(self) -> None:
        """验证所有实体的字段名冲突（运行时检查）。"""
        for entity_cfg in self.er_diagram.configs:
            self._validate_entity_fields(entity_cfg)

    def _validate_entity_fields(self, entity_cfg) -> None:
        """验证单个实体的字段冲突。"""
        # 收集所有字段（标量 + 关系）
        try:
            scalar_fields = set(get_type_hints(entity_cfg.kls).keys())
        except Exception:
            scalar_fields = set()

        relationship_fields = set()
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship) and rel.default_field_name:
                relationship_fields.add(rel.default_field_name)

        # 检查交集
        conflicts = scalar_fields & relationship_fields
        if conflicts:
            field_name = next(iter(conflicts))
            raise FieldNameConflictError(
                message=f"Field name conflict in {entity_cfg.kls.__name__}: '{field_name}'",
                entity_name=entity_cfg.kls.__name__,
                field_name=field_name,
                conflict_type="SCALAR_CONFLICT"
            )

    def _collect_nested_pydantic_types(self, processed_types: set) -> set:
        """
        递归收集所有嵌套的 Pydantic BaseModel 类型

        Args:
            processed_types: 已经处理过的类型集合

        Returns:
            所有发现的嵌套 Pydantic 类型集合
        """
        nested_types = set()
        types_to_check = list(processed_types)

        while types_to_check:
            current_type = types_to_check.pop()

            # 获取当前类型的所有字段提示
            try:
                type_hints = get_type_hints(current_type)
            except Exception:
                continue

            for field_type in type_hints.values():
                # 使用 get_core_types 处理所有包装类型
                core_types = get_core_types(field_type)

                for core_type in core_types:
                    # 检查是否是 Pydantic BaseModel
                    if safe_issubclass(core_type, BaseModel):
                        if core_type not in processed_types and core_type not in nested_types:
                            nested_types.add(core_type)
                            types_to_check.append(core_type)

        return nested_types

    def _build_type_definition_for_class(self, kls: type) -> str:
        """
        为任意 Pydantic BaseModel 类生成 GraphQL 类型定义

        Args:
            kls: Pydantic BaseModel 类

        Returns:
            GraphQL 类型定义字符串
        """
        fields = []

        # 获取类的所有字段提示
        try:
            type_hints = get_type_hints(kls)
        except Exception:
            type_hints = {}

        # 处理所有字段
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            # 映射 Python 类型到 GraphQL 类型
            gql_type = self._map_python_type_to_gql(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        return f"type {kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _collect_input_types(self) -> set:
        """
        收集所有方法参数中的 BaseModel 类型作为 Input Types

        Returns:
            所有需要生成 input 定义的 BaseModel 类型集合
        """
        input_types = set()
        visited = set()

        def collect_from_type(param_type):
            """递归收集类型中的 BaseModel"""
            # 使用 get_core_types 处理包装类型
            core_types = get_core_types(param_type)

            for core_type in core_types:
                if safe_issubclass(core_type, BaseModel):
                    type_name = core_type.__name__
                    if type_name not in visited:
                        visited.add(type_name)
                        input_types.add(core_type)

                        # 递归收集嵌套的 BaseModel 类型
                        try:
                            type_hints = get_type_hints(core_type)
                            for field_type in type_hints.values():
                                collect_from_type(field_type)
                        except Exception:
                            pass

        # 遍历所有实体的 @query 和 @mutation 方法
        for entity_cfg in self.er_diagram.configs:
            # 收集 @query 方法的参数类型
            query_methods = self._extract_query_methods(entity_cfg.kls)
            for method_info in query_methods:
                for param in method_info.get('params', []):
                    # 获取原始参数类型（从 method 签名）
                    method = method_info.get('method')
                    if method:
                        try:
                            sig = inspect.signature(method)
                            param_name = param['name']
                            if param_name in sig.parameters:
                                param_type = sig.parameters[param_name].annotation
                                if param_type != inspect.Parameter.empty:
                                    collect_from_type(param_type)
                        except Exception:
                            pass

            # 收集 @mutation 方法的参数类型
            mutation_methods = self._extract_mutation_methods(entity_cfg.kls)
            for method_info in mutation_methods:
                for param in method_info.get('params', []):
                    method = method_info.get('method')
                    if method:
                        try:
                            sig = inspect.signature(method)
                            param_name = param['name']
                            if param_name in sig.parameters:
                                param_type = sig.parameters[param_name].annotation
                                if param_type != inspect.Parameter.empty:
                                    collect_from_type(param_type)
                        except Exception:
                            pass

        return input_types

    def _build_input_definition(self, kls: type) -> str:
        """
        为 Pydantic BaseModel 类生成 GraphQL Input 类型定义

        Args:
            kls: Pydantic BaseModel 类

        Returns:
            GraphQL input 类型定义字符串
        """
        fields = []

        # 获取类的所有字段提示
        try:
            type_hints = get_type_hints(kls)
        except Exception:
            type_hints = {}

        # 处理所有字段
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            # 映射 Python 类型到 GraphQL 类型（用于 input）
            gql_type = self._map_python_type_to_gql_for_input(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        return f"input {kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _map_python_type_to_gql_for_input(self, python_type: type) -> str:
        """
        将 Python 类型映射到 GraphQL 类型（用于 Input 类型）

        与 _map_python_type_to_gql 类似，但处理嵌套的 Input 类型

        Args:
            python_type: Python 类型

        Returns:
            GraphQL 类型字符串
        """
        from typing import Union

        origin = get_origin(python_type)

        # 处理 Optional[T] (Union[T, None])
        if origin is Union:
            args = get_args(python_type)
            # 过滤掉 NoneType
            non_none_args = [a for a in args if a is not type(None)]
            if non_none_args:
                # 取第一个非 None 类型，递归处理（不加 ! 后缀，因为它是可选的）
                inner_gql = self._map_python_type_to_gql_for_input(non_none_args[0])
                # 移除 ! 后缀表示可选
                return inner_gql.rstrip('!')

        # 处理 list[T]
        if origin is list:
            args = get_args(python_type)
            if args:
                inner_gql = self._map_python_type_to_gql_for_input(args[0])
                # 确保内部类型有 ! 后缀
                if not inner_gql.endswith('!'):
                    inner_gql = inner_gql + '!'
                return f"[{inner_gql}]!"
            return "[String!]!"

        # 处理核心类型
        core_types = get_core_types(python_type)
        if not core_types:
            return "String!"

        core_type = core_types[0]

        if safe_issubclass(core_type, BaseModel):
            # Input 类型引用其他 Input 类型
            return f"{core_type.__name__}!"
        else:
            # 标量类型
            scalar_name = map_scalar_type(core_type)
            return f"{scalar_name}!"


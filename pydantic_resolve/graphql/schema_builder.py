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

        type_defs = []
        query_defs = []
        processed_types = set()  # 跟踪已处理的类型，避免重复

        # 生成所有实体类型
        for entity_cfg in self.er_diagram.configs:
            type_def = self._build_type_definition(entity_cfg)
            type_defs.append(type_def)
            processed_types.add(entity_cfg.kls)

            # 提取该实体的 @query 方法
            query_methods = self._extract_query_methods(entity_cfg.kls)
            for method in query_methods:
                query_defs.append(self._build_query_def(method))

        # 收集并生成所有嵌套的 Pydantic 类型
        nested_types = self._collect_nested_pydantic_types(processed_types)
        for nested_type in nested_types:
            if nested_type not in processed_types:
                type_def = self._build_type_definition_for_class(nested_type)
                type_defs.append(type_def)
                processed_types.add(nested_type)

        # 组装完整的 Schema
        schema = "\n".join(type_defs) + "\n\n"
        schema += "type Query {\n"
        if query_defs:
            schema += "\n".join(f"  {qd}" for qd in query_defs) + "\n"
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

                if is_required:
                    param_str = f"${param_name}: {gql_type}!"
                else:
                    param_str = f"${param_name}: {gql_type}"

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


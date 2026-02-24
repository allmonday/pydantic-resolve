"""
GraphQL Schema generator from ERD and @query decorated methods.
"""

import inspect
from typing import Dict, List, Union, get_args, get_origin, get_type_hints

from ..utils.er_diagram import ErDiagram, Relationship


class SchemaBuilder:
    """从 ERD 和 @query 装饰的方法生成 GraphQL Schema"""

    # Python 类型到 GraphQL 类型的映射
    PYTHON_TO_GQL_TYPES = {
        int: 'Int',
        str: 'String',
        float: 'Float',
        bool: 'Boolean',
    }

    def __init__(self, er_diagram: ErDiagram):
        """
        Args:
            er_diagram: 实体关系图
        """
        self.er_diagram = er_diagram

    def build_schema(self) -> str:
        """
        生成完整的 GraphQL Schema

        Returns:
            GraphQL Schema 字符串
        """
        type_defs = []
        query_defs = []

        # 生成所有实体类型
        for entity_cfg in self.er_diagram.configs:
            type_def = self._build_type_definition(entity_cfg)
            type_defs.append(type_def)

            # 提取该实体的 @query 方法
            query_methods = self._extract_query_methods(entity_cfg.kls)
            for method in query_methods:
                query_defs.append(self._build_query_def(method))

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
                'method': method  # 保存原始的 classmethod 对象
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
        """将 Python 类型映射到 GraphQL 类型"""
        # 处理 Optional 类型
        origin = getattr(python_type, '__origin__', None)

        if origin is not None:
            # Optional[X] 或 Union[X, None]
            args = getattr(python_type, '__args__', [])
            if origin.__name__ in ['Union', 'Optional']:
                # 取第一个非 None 类型
                for arg in args:
                    if arg is not type(None):
                        base_type = self._map_python_type_to_gql(arg)
                        return base_type
            elif origin.__name__ == 'list':
                # List[X]
                args = getattr(python_type, '__args__', [])
                if args:
                    inner_type = self._map_python_type_to_gql(args[0])
                    return f"[{inner_type}]!"
            elif origin.__name__ == 'dict':
                # Dict
                return 'String'

        # 基础类型
        if python_type in self.PYTHON_TO_GQL_TYPES:
            gql_type = self.PYTHON_TO_GQL_TYPES[python_type]
            return f"{gql_type}!"

        # 处理字符串类型
        if python_type is str or python_type == 'str':
            return "String!"

        # 处理 List 类型（作为列表类型提示）
        if hasattr(python_type, '__origin__') and python_type.__origin__ is list:
            args = getattr(python_type, '__args__', [])
            if args:
                inner_type = self._map_python_type_to_gql(args[0])
                return f"[{inner_type}]!"

        # 默认为字符串
        return "String!"

    def _map_return_type_to_gql(self, return_type: type) -> str:
        """映射返回类型到 GraphQL 类型"""
        origin = getattr(return_type, '__origin__', None)

        # 处理 List[X]
        if origin is list or (hasattr(origin, '__name__') and origin.__name__ == 'list'):
            args = getattr(return_type, '__args__', [])
            if args:
                inner_type = args[0]
                inner_gql = self._map_python_type_to_gql(inner_type)
                return f"[{inner_gql}]"

        # 处理 Optional[X]
        if origin is Union or (hasattr(origin, '__name__') and origin.__name__ in ['Union', 'Optional']):
            args = getattr(return_type, '__args__', [])
            for arg in args:
                if arg is not type(None):
                    return self._map_python_type_to_gql(arg)

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

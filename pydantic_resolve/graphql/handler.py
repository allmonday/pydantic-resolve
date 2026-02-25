"""
GraphQL handler - coordinates all components and provides FastAPI integration.
"""

import asyncio
import logging
import os
import re
from typing import Any, Callable, Dict, List, Tuple, Optional, TYPE_CHECKING
from typing import get_origin
from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from .type_mapping import map_scalar_type, is_list_type, get_graphql_type_description

if TYPE_CHECKING:
    from fastapi import APIRouter

from ..resolver import Resolver
from ..utils.er_diagram import ErDiagram
from .query_parser import QueryParser
from .schema_builder import SchemaBuilder
from .response_builder import ResponseBuilder
from .exceptions import GraphQLError

logger = logging.getLogger(__name__)

# GraphQL 标量类型定义
SCALAR_TYPES = {
    "Int": {
        "kind": "SCALAR",
        "name": "Int",
        "description": "The `Int` scalar type represents non-fractional signed whole numeric values.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
    "Float": {
        "kind": "SCALAR",
        "name": "Float",
        "description": "The `Float` scalar type represents signed double-precision fractional values.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
    "String": {
        "kind": "SCALAR",
        "name": "String",
        "description": "The `String` scalar type represents textual data.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
    "Boolean": {
        "kind": "SCALAR",
        "name": "Boolean",
        "description": "The `Boolean` scalar type represents `true` or `false`.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
    "ID": {
        "kind": "SCALAR",
        "name": "ID",
        "description": "The `ID` scalar type represents a unique identifier.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
}

# FastAPI 是可选依赖
try:
    from fastapi import APIRouter
    from fastapi.responses import PlainTextResponse
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    APIRouter = None  # type: ignore
    PlainTextResponse = None  # type: ignore
    BaseModel = None  # type: ignore
    FASTAPI_AVAILABLE = False


if FASTAPI_AVAILABLE:
    class GraphQLRequest(BaseModel):
        """GraphQL 请求模型"""
        query: str
        variables: Optional[Dict[str, Any]] = None
        operation_name: Optional[str] = None
else:
    GraphQLRequest = None  # type: ignore


class GraphQLHandler:
    """
    GraphQL 查询处理器

    协调所有组件，解析查询、执行 @query 方法、构建响应模型、解析关联数据
    """

    def __init__(
        self,
        er_diagram: ErDiagram,
        resolver_class: type[Resolver] = Resolver
    ):
        """
        Args:
            er_diagram: 实体关系图
            resolver_class: 自定义 Resolver 类（可选）
        """
        self.er_diagram = er_diagram
        self.parser = QueryParser(er_diagram)
        self.builder = ResponseBuilder(er_diagram)
        self.schema_builder = SchemaBuilder(er_diagram)
        self.resolver_class = resolver_class

        # 构建查询方法映射: { 'users': (UserEntity, UserEntity.get_all) }
        self.query_map = self._build_query_map()

    def _build_query_map(self) -> Dict[str, Tuple[type, Callable]]:
        """
        扫描所有 Entity，构建查询名称到方法的映射

        Returns:
            查询名称到 (实体类, 方法) 的映射字典
        """
        query_map = {}
        for entity_cfg in self.er_diagram.configs:
            methods = self.schema_builder._extract_query_methods(entity_cfg.kls)
            for method_info in methods:
                query_name = method_info['name']
                query_map[query_name] = (entity_cfg.kls, method_info['method'])
        return query_map

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行 GraphQL 查询

        Args:
            query: GraphQL 查询字符串
            variables: 查询变量
            operation_name: 操作名称

        Returns:
            GraphQL 响应格式：{"data": {...}, "errors": [...]}
        """
        logger.debug(f"Executing GraphQL query: {query[:100]}...")
        try:
            # 检测内省查询
            is_introspection = self._is_introspection_query(query)

            if is_introspection:
                logger.debug("Processing introspection query")
                # 使用 graphql-core 的完整功能执行内省查询
                return await self._execute_introspection(query, variables, operation_name)
            else:
                logger.debug("Processing custom query")
                # 使用自定义逻辑执行普通查询
                return await self._execute_custom_query(query)

        except GraphQLError as e:
            logger.warning(f"GraphQL error: {e.message}")
            return {
                "data": None,
                "errors": [e.to_dict()]
            }
        except Exception as e:
            logger.exception("Unexpected error during GraphQL query execution")
            return {
                "data": None,
                "errors": [
                    {
                        "message": str(e),
                        "extensions": {"code": type(e).__name__}
                    }
                ]
            }

    def _is_introspection_query(self, query: str) -> bool:
        """检测是否为内省查询"""
        query_stripped = query.strip()
        # 检查是否包含 __schema, __type, __typename 等内省字段
        introspection_keywords = ["__schema", "__type", "__typename"]
        return any(keyword in query_stripped for keyword in introspection_keywords)

    def _parse_introspection_query(self, query: str) -> Dict[str, Any]:
        """解析内省查询，提取请求的字段"""
        from graphql import parse as parse_graphql

        try:
            parse_graphql(query)

            # 简化：检查查询是否请求 __type
            requests_type = "__type(" in query or '__type (' in query.replace('"', "'")

            return {
                "requests_schema": "__schema" in query,
                "requests_type": requests_type
            }
        except Exception:
            # 解析失败，假设两者都请求
            return {
                "requests_schema": True,
                "requests_type": True
            }

    async def _execute_introspection(
        self,
        query: str,
        variables: Optional[Dict[str, Any]],
        operation_name: Optional[str]
    ) -> Dict[str, Any]:
        """执行内省查询 - 返回完整的内省数据以支持 GraphiQL"""

        # 解析查询以确定请求的内容
        query_info = self._parse_introspection_query(query)

        # 构建响应数据
        data = {}

        if query_info["requests_schema"]:
            data["__schema"] = {
                "queryType": {
                    "name": "Query",
                    "kind": "OBJECT"
                },
                "mutationType": None,
                "subscriptionType": None,
                "types": self._get_introspection_types(),
                "directives": []  # 暂不支持 directives
            }

        if query_info["requests_type"]:
            # 尝试从查询中提取类型名称
            type_name = self._extract_type_name_from_query(query)
            if type_name:
                data["__type"] = self._get_introspection_type(type_name)

        return {
            "data": data,
            "errors": None
        }

    def _extract_type_name_from_query(self, query: str) -> Optional[str]:
        """从查询中提取类型名称"""
        # 匹配 __type(name: "TypeName")
        match = re.search(r'__type\s*\(\s*name\s*:\s*["\']([^"\']+)["\']', query)
        if match:
            return match.group(1)

        # 匹配 __type(name: 'TypeName')
        match = re.search(r"__type\s*\(\s*name\s*:\s*'([^']+)'", query)
        if match:
            return match.group(1)

        return None

    def _get_introspection_type(self, type_name: str) -> Optional[Dict[str, Any]]:
        """获取指定类型的内省信息"""
        # 检查标量类型
        if type_name in SCALAR_TYPES:
            return SCALAR_TYPES[type_name]

        # 收集所有类型（包括嵌套的 Pydantic 类型）
        collected_types = {}
        for entity_cfg in self.er_diagram.configs:
            collected_types[entity_cfg.kls.__name__] = entity_cfg.kls

        # 收集嵌套类型
        additional_types = self._collect_nested_pydantic_types(list(collected_types.values()))
        for name, cls in additional_types.items():
            if name not in collected_types:
                collected_types[name] = cls

        # 检查实体类型
        if type_name in collected_types:
            entity = collected_types[type_name]
            return {
                "kind": "OBJECT",
                "name": type_name,
                "description": f"{type_name} entity",
                "fields": self._get_introspection_fields(entity),
                "inputFields": None,
                "interfaces": [],  # OBJECT types must have interfaces as array
                "enumValues": None,
                "possibleTypes": None
            }

        # 检查 Query 类型
        if type_name == "Query":
            return {
                "kind": "OBJECT",
                "name": "Query",
                "description": "Root query type",
                "fields": self._get_introspection_query_fields(),
                "inputFields": None,
                "interfaces": [],  # OBJECT types must have interfaces as array
                "enumValues": None,
                "possibleTypes": None
            }

        return None

    def _get_introspection_types(self):
        """获取内省类型列表"""
        types = []

        # 添加标量类型
        types.extend([SCALAR_TYPES[name] for name in ["Int", "Float", "String", "Boolean", "ID"]])

        # 收集所有实体类型（包括 ERD 中的实体和字段中引用的嵌套 Pydantic 模型）
        collected_types = {}

        # 首先收集 ERD 中的实体
        for entity_cfg in self.er_diagram.configs:
            collected_types[entity_cfg.kls.__name__] = entity_cfg.kls

        # 递归收集所有字段中引用的 Pydantic BaseModel 类型
        additional_types = self._collect_nested_pydantic_types(list(collected_types.values()))
        for type_name, type_class in additional_types.items():
            if type_name not in collected_types:
                collected_types[type_name] = type_class

        # 为所有收集的类型生成 introspection
        for type_name, entity in collected_types.items():
            entity_type = {
                "kind": "OBJECT",
                "name": entity.__name__,
                "description": f"{entity.__name__} entity",
                "fields": self._get_introspection_fields(entity),
                "inputFields": None,
                "interfaces": [],  # OBJECT types must have interfaces as array
                "enumValues": None,
                "possibleTypes": None
            }
            types.append(entity_type)

        # 添加 Query 类型
        types.append({
            "kind": "OBJECT",
            "name": "Query",
            "description": "Root query type",
            "fields": self._get_introspection_query_fields(),
            "inputFields": None,
            "interfaces": [],  # OBJECT types must have interfaces as array
            "enumValues": None,
            "possibleTypes": None
        })

        return types

    def _is_pydantic_basemodel(self, type_hint: Any) -> bool:
        """
        检查类型是否是 Pydantic BaseModel

        Args:
            type_hint: 类型提示

        Returns:
            是否是 Pydantic BaseModel
        """
        # 使用 get_core_types 提取核心类型，处理 Optional[T]、list[T]、Annotated[T, ...] 等包装
        core_types = get_core_types(type_hint)
        return any(safe_issubclass(t, BaseModel) for t in core_types)

    def _extract_list_element_type(self, field_type: Any) -> Optional[type]:
        """
        从 list[T] 中提取元素类型 T

        Args:
            field_type: 字段类型（可能是 list[T]）

        Returns:
            元素类型，如果不是 list 则返回 None
        """
        from typing import get_args

        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args:
                return args[0]
        return None

    def _collect_nested_pydantic_types(self, entities: list, visited: Optional[set] = None) -> Dict[str, type]:
        """
        递归收集所有实体字段中引用的 Pydantic BaseModel 类型

        Args:
            entities: 要扫描的实体列表
            visited: 已访问的类型名称集合（避免循环引用）

        Returns:
            类型名到类型类的映射字典
        """
        if visited is None:
            visited = set()

        collected = {}

        for entity in entities:
            type_name = entity.__name__
            if type_name in visited:
                continue
            visited.add(type_name)

            # 扫描实体的所有字段
            if hasattr(entity, '__annotations__'):
                for field_name, field_type in entity.__annotations__.items():
                    if field_name.startswith('__'):
                        continue

                    # 使用 get_core_types 处理所有包装类型（Optional, list, Annotated 等）
                    # 然后检查每个核心类型是否是 Pydantic BaseModel
                    core_types = get_core_types(field_type)
                    for core_type in core_types:
                        if safe_issubclass(core_type, BaseModel):
                            if core_type.__name__ not in collected and core_type.__name__ not in visited:
                                collected[core_type.__name__] = core_type

        # 递归收集新发现的类型的嵌套类型
        if collected:
            nested_types = self._collect_nested_pydantic_types(list(collected.values()), visited)
            collected.update(nested_types)

        return collected

    def _get_introspection_fields(self, entity):
        """获取实体的内省字段"""
        from ..utils.er_diagram import Relationship

        fields = []

        # 1. 处理标量字段（来自 __annotations__）
        if hasattr(entity, '__annotations__'):
            for field_name, field_type in entity.__annotations__.items():
                if field_name.startswith('__'):
                    continue

                # 跳过关系字段（由关系部分处理）
                is_relationship_field = False
                entity_cfg = None
                for cfg in self.er_diagram.configs:
                    if cfg.kls == entity:
                        entity_cfg = cfg
                        break
                if entity_cfg:
                    for rel in entity_cfg.relationships:
                        if isinstance(rel, Relationship) and hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                            is_relationship_field = True
                            break
                if is_relationship_field:
                    continue

                # 构建字段类型信息
                type_def = self._build_graphql_type(field_type)
                fields.append({
                    "name": field_name,
                    "description": None,
                    "args": [],
                    "type": type_def,
                    "isDeprecated": False,
                    "deprecationReason": None
                })

        # 2. 处理关联关系（来自 __relationships__）
        entity_cfg = None
        for cfg in self.er_diagram.configs:
            if cfg.kls == entity:
                entity_cfg = cfg
                break

        if entity_cfg:
            for rel in entity_cfg.relationships:
                if isinstance(rel, Relationship):
                    # 只有提供了 default_field_name 的关系才暴露给 GraphQL
                    if not hasattr(rel, 'default_field_name') or not rel.default_field_name:
                        continue

                    field_name = rel.default_field_name
                    type_def = self._build_graphql_type(rel.target_kls)

                    fields.append({
                        "name": field_name,
                        "description": None,
                        "args": [],
                        "type": type_def,
                        "isDeprecated": False,
                        "deprecationReason": None
                    })

        return fields

    def _build_graphql_type(self, field_type: Any) -> Dict[str, Any]:
        """
        将 Python 类型映射为 GraphQL 类型定义

        Args:
            field_type: Python 类型（可以是 list[T]、Optional[T]、T 等）

        Returns:
            GraphQL 类型定义字典
        """
        # 使用 get_core_types 处理所有包装类型
        core_types = get_core_types(field_type)
        if not core_types:
            # 无法确定类型，默认为 String
            return {
                "kind": "SCALAR",
                "name": "String",
                "description": None,
                "ofType": None
            }

        # 获取核心类型
        core_type = core_types[0]

        # 检查是否是 list[T]
        if is_list_type(field_type):
            # list[T] -> LIST 类型
            if safe_issubclass(core_type, BaseModel):
                # list[Entity] -> LIST -> OBJECT
                return {
                    "kind": "LIST",
                    "name": None,
                    "description": None,
                    "ofType": {
                        "kind": "OBJECT",
                        "name": core_type.__name__,
                        "description": f"{core_type.__name__} entity",
                        "ofType": None
                    }
                }
            else:
                # list[Scalar] -> LIST -> SCALAR
                scalar_name = map_scalar_type(core_type)
                return {
                    "kind": "LIST",
                    "name": None,
                    "description": None,
                    "ofType": {
                        "kind": "SCALAR",
                        "name": scalar_name,
                        "description": None,
                        "ofType": None
                    }
                }
        else:
            # T (非 list)
            if safe_issubclass(core_type, BaseModel):
                # Entity -> OBJECT
                return {
                    "kind": "OBJECT",
                    "name": core_type.__name__,
                    "description": f"{core_type.__name__} entity",
                    "ofType": None
                }
            else:
                # Scalar -> SCALAR
                scalar_name = map_scalar_type(core_type)
                # 添加特殊描述
                desc = get_graphql_type_description(scalar_name)
                if "dict" in str(core_type).lower():
                    scalar_name = "String"
                    desc = "JSON string representation"

                return {
                    "kind": "SCALAR",
                    "name": scalar_name,
                    "description": desc,
                    "ofType": None
                }

    def _get_introspection_query_fields(self):
        """获取 Query 类型的内省字段"""
        fields = []

        for query_name, (entity, method) in self.query_map.items():
            import inspect
            sig = inspect.signature(method)

            # 构建参数列表
            args = []
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue

                # 确定参数类型
                param_type = "String"
                param_kind = "SCALAR"

                # 尝试从类型注解获取类型
                if param.annotation != inspect.Parameter.empty:
                    annotation_str = str(param.annotation)
                    if "int" in annotation_str.lower():
                        param_type = "Int"
                    elif "bool" in annotation_str.lower():
                        param_type = "Boolean"
                    elif "float" in annotation_str.lower():
                        param_type = "Float"

                # 检查是否有默认值
                has_default = param.default != inspect.Parameter.empty

                args.append({
                    "name": param_name,
                    "description": None,
                    "type": {
                        "kind": param_kind,
                        "name": param_type,
                        "ofType": None
                    },
                    "defaultValue": None if not has_default else str(param.default)
                })

            # 确定返回类型
            return_type_str = str(sig.return_annotation) if sig.return_annotation != sig.empty else "String"
            return_kind = "SCALAR"
            return_name = "String"
            of_type = None

            if "list" in return_type_str.lower():
                return_kind = "LIST"
                return_name = None
                # LIST 类型必须有 ofType 指向元素类型
                if hasattr(entity, '__name__'):
                    of_type = {
                        "kind": "OBJECT",
                        "name": entity.__name__,
                        "ofType": None
                    }
                else:
                    of_type = {
                        "kind": "SCALAR",
                        "name": "String",
                        "ofType": None
                    }
            elif hasattr(entity, '__name__'):
                return_name = entity.__name__
                return_kind = "OBJECT"

            type_def = {
                "kind": return_kind,
                "name": return_name,
                "description": None,
                "ofType": of_type
            }

            # 根据类型种类添加其他必需字段
            if return_kind == "SCALAR":
                type_def["fields"] = None
                type_def["inputFields"] = None
                type_def["interfaces"] = None
                type_def["enumValues"] = None
                type_def["possibleTypes"] = None
            elif return_kind == "OBJECT":
                type_def["fields"] = self._get_introspection_fields(entity)
                type_def["inputFields"] = None
                type_def["interfaces"] = None
                type_def["enumValues"] = None
                type_def["possibleTypes"] = None
            elif return_kind == "LIST":
                type_def["fields"] = None
                type_def["inputFields"] = None
                type_def["interfaces"] = None
                type_def["enumValues"] = None
                type_def["possibleTypes"] = None

            fields.append({
                "name": query_name,
                "description": f"Query for {query_name}",
                "args": args,
                "type": type_def,
                "isDeprecated": False,
                "deprecationReason": None
            })

        return fields

    async def _execute_custom_query(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """
        执行自定义查询，采用优化的两阶段执行：
        - 阶段 1（串行）：查询方法执行、模型构建、数据转换
        - 阶段 2（并发）：并行执行所有根查询的 Resolver
        """
        logger.info("Starting custom query execution with concurrent optimization")

        # 1. 解析查询
        parsed = self.parser.parse(query)
        logger.debug(f"Query parsed: {len(parsed.field_tree)} root fields found")

        # 2. 初始化结果
        errors = []
        data = {}

        # ===== 阶段 1：串行准备 =====
        logger.info("[Phase 1] Starting serial preparation phase")

        preparation_results = {}  # query_name -> (typed_data, is_list)

        for root_query_name, root_field_selection in parsed.field_tree.items():
            try:
                # 检查查询是否存在
                if root_query_name not in self.query_map:
                    errors.append({
                        "message": f"未知的查询: {root_query_name}",
                        "extensions": {"code": "UNKNOWN_QUERY"}
                    })
                    logger.warning(f"[Phase 1] Unknown query: {root_query_name}")
                    continue

                entity, query_method = self.query_map[root_query_name]

                # 准备查询解析
                typed_data, error_msg, error_dict = await self._prepare_query_resolution(
                    root_query_name=root_query_name,
                    root_field_selection=root_field_selection,
                    entity=entity,
                    query_method=query_method
                )

                if error_dict:
                    errors.append(error_dict)
                else:
                    # 存储用于阶段 2
                    is_list = isinstance(typed_data, list)
                    preparation_results[root_query_name] = (typed_data, is_list)

            except GraphQLError as e:
                errors.append(e.to_dict())
            except Exception as e:
                logger.exception(f"Unexpected error in Phase 1 for {root_query_name}")
                errors.append({
                    "message": str(e),
                    "extensions": {"code": type(e).__name__}
                })

        logger.info(f"[Phase 1] Completed: {len(preparation_results)} queries prepared, {len(errors)} errors")

        # ===== 阶段 2：并发解析 =====
        logger.info("[Phase 2] Starting concurrent resolution phase")

        if preparation_results:
            # 构建解析任务
            resolution_tasks = [
                (name, data, is_list)
                for name, (data, is_list) in preparation_results.items()
            ]

            # 并发执行所有解析
            resolution_map = await self._execute_concurrent_resolutions(resolution_tasks)

            # 收集结果和错误
            for query_name, (result_data, error_dict) in resolution_map.items():
                if error_dict:
                    errors.append(error_dict)
                else:
                    data[query_name] = result_data

        logger.info(f"[Phase 2] Completed: {len(data)} queries resolved successfully")

        # 3. 格式化响应
        response = {
            "data": data if data else None,
            "errors": errors if errors else None
        }

        logger.info(f"Query execution complete: {len(data) if data else 0} successful, {len(errors) if errors else 0} errors")
        return response

    async def _execute_query_method(
        self,
        method: Callable,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        执行 @query 方法

        Args:
            method: @query 装饰的方法（可能是 classmethod 或普通函数）
            arguments: 参数字典

        Returns:
            查询结果
        """
        logger.debug(f"Executing query method with arguments: {arguments}")
        try:
            # schema_builder 已经提取了底层函数（对于 classmethod 是 __func__）
            # 直接调用，第一个参数（cls/self）传入 None
            return await method(None, **arguments)
        except Exception as e:
            logger.error(f"Query method execution failed: {e}")
            raise GraphQLError(
                f"查询执行失败: {e}",
                extensions={"code": "EXECUTION_ERROR"}
            )

    async def _prepare_query_resolution(
        self,
        root_query_name: str,
        root_field_selection: Any,
        entity: type,
        query_method: Callable
    ) -> Tuple[Optional[Any], Optional[str], Optional[Dict]]:
        """
        准备查询解析（阶段 1：串行）

        Args:
            root_query_name: 根查询字段名称
            root_field_selection: 解析的字段选择
            entity: 实体类
            query_method: @query 装饰的方法

        Returns:
            Tuple of (typed_data, error_message, error_dict)
            - 成功: (typed_data, None, None)
            - 失败: (None, error_message, error_dict)
        """
        logger.debug(f"[Phase 1] Preparing query: {root_query_name}")

        try:
            # 1. 执行查询方法
            args = root_field_selection.arguments or {}
            root_data = await self._execute_query_method(query_method, args)
            logger.debug(f"[Phase 1] Query method executed: {root_query_name}")

            # 2. 构建响应模型
            response_model = self.builder.build_response_model(
                entity=entity,
                field_selection=root_field_selection
            )
            logger.debug(f"[Phase 1] Response model built: {root_query_name}")

            # 3. 转换为响应模型
            if isinstance(root_data, list):
                typed_data = [
                    response_model.model_validate(
                        d.model_dump() if hasattr(d, 'model_dump') else d
                    )
                    for d in root_data
                ]
            elif root_data is not None:
                typed_data = response_model.model_validate(
                    root_data.model_dump() if hasattr(root_data, 'model_dump') else root_data
                )
            else:
                typed_data = None

            logger.debug(f"[Phase 1] Data transformed: {root_query_name}")
            return typed_data, None, None

        except GraphQLError as e:
            logger.warning(f"[Phase 1] GraphQL error preparing {root_query_name}: {e.message}")
            return None, e.message, e.to_dict()
        except Exception as e:
            logger.exception(f"[Phase 1] Unexpected error preparing {root_query_name}")
            error_dict = {
                "message": str(e),
                "extensions": {"code": type(e).__name__}
            }
            return None, str(e), error_dict

    async def _resolve_query_data(
        self,
        root_query_name: str,
        typed_data: Any,
        is_list: bool
    ) -> Tuple[Optional[Any], Optional[Dict]]:
        """
        解析查询数据（阶段 2：并发）

        Args:
            root_query_name: 根查询字段名称
            typed_data: 类型化的 Pydantic 数据
            is_list: 数据是否为列表

        Returns:
            Tuple of (result_data, error_dict)
            - 成功: (result_data, None)
            - 失败: (None, error_dict)
        """
        logger.debug(f"[Phase 2] Resolving query: {root_query_name}")

        try:
            result_data = None

            if typed_data is not None:
                resolver = self.resolver_class()

                if is_list:
                    result = await resolver.resolve(typed_data)
                    if result is not None:
                        result_data = [r.model_dump(by_alias=True) for r in result]
                    else:
                        result_data = []
                else:
                    result = await resolver.resolve(typed_data)
                    if result is not None:
                        result_data = result.model_dump(by_alias=True)
                    else:
                        result_data = None
            else:
                result_data = [] if is_list else None

            logger.debug(f"[Phase 2] Query resolved: {root_query_name}")
            return result_data, None

        except Exception as e:
            logger.exception(f"[Phase 2] Error resolving {root_query_name}")
            error_dict = {
                "message": f"Resolution failed for {root_query_name}: {str(e)}",
                "extensions": {"code": type(e).__name__}
            }
            return None, error_dict

    async def _execute_concurrent_resolutions(
        self,
        resolution_tasks: List[Tuple[str, Any, bool]]
    ) -> Dict[str, Tuple[Optional[Any], Optional[Dict]]]:
        """
        并发执行多个查询解析，使用信号量控制并发数

        Args:
            resolution_tasks: List of (query_name, typed_data, is_list) tuples

        Returns:
            Dict mapping query_name to (result_data, error_dict)
        """
        if not resolution_tasks:
            return {}

        logger.info(f"[Phase 2] Starting concurrent resolution of {len(resolution_tasks)} queries")

        # 资源控制：只有用户明确设置环境变量时才限制并发 Resolver 实例数量
        max_concurrency_str = os.getenv("PYDANTIC_RESOLVE_MAX_CONCURRENT_QUERIES")
        if max_concurrency_str:
            max_concurrency = int(max_concurrency_str)
            semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency > 0 else None
        else:
            semaphore = None

        async def resolve_with_semaphore(query_name: str, typed_data: Any, is_list: bool):
            if semaphore:
                async with semaphore:
                    return await self._resolve_query_data(query_name, typed_data, is_list)
            else:
                return await self._resolve_query_data(query_name, typed_data, is_list)

        # 并发执行所有解析任务
        results = await asyncio.gather(
            *[resolve_with_semaphore(name, data, is_list) for name, data, is_list in resolution_tasks],
            return_exceptions=True
        )

        # 处理结果并映射到查询名称
        query_names = [name for name, _, _ in resolution_tasks]
        resolution_map = {}

        for query_name, result in zip(query_names, results):
            if isinstance(result, Exception):
                logger.exception(f"[Phase 2] Unexpected exception for {query_name}")
                error_dict = {
                    "message": f"Unexpected error: {str(result)}",
                    "extensions": {"code": type(result).__name__}
                }
                resolution_map[query_name] = (None, error_dict)
            else:
                resolution_map[query_name] = result

        logger.info("[Phase 2] Completed concurrent resolution")
        return resolution_map


def create_graphql_route(
    er_diagram: ErDiagram,
    path: str = "/graphql"
):
    """
    创建 FastAPI GraphQL 路由

    Args:
        er_diagram: 实体关系图
        path: 路由路径

    Returns:
        FastAPI APIRouter

    使用示例:
        ```python
        from fastapi import FastAPI
        from pydantic_resolve import base_entity, config_global_resolver
        from pydantic_resolve.graphql import create_graphql_route

        app = FastAPI()
        BaseEntity = base_entity()
        config_global_resolver(BaseEntity.get_diagram())

        graphql_router = create_graphql_route(BaseEntity.get_diagram())
        app.include_router(graphql_router)
        ```
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI is required for create_graphql_route. "
            "Please install it with: pip install fastapi"
        )

    router = APIRouter()
    handler = GraphQLHandler(er_diagram)
    schema_builder = SchemaBuilder(er_diagram)

    @router.post(path)
    async def graphql_endpoint(req: GraphQLRequest):
        """GraphQL 查询端点"""
        result = await handler.execute(
            query=req.query,
            variables=req.variables,
            operation_name=req.operation_name
        )
        return result

    @router.get("/schema", response_class=None)
    async def graphql_schema():
        """GraphQL Schema 端点（返回 SDL 格式）"""
        schema_sdl = schema_builder.build_schema()
        return PlainTextResponse(
            content=schema_sdl,
            media_type="text/plain; charset=utf-8"
        )

    return router

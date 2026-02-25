"""
Dynamic Pydantic model builder based on GraphQL field selection.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, get_type_hints, get_origin, get_args, Annotated
from pydantic import BaseModel, create_model, Field
from functools import lru_cache

from ..constant import ENSURE_SUBSET_REFERENCE
from ..utils.er_diagram import ErDiagram, Relationship, LoadBy, ErLoaderPreGenerator
from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from .types import FieldSelection


class ResponseBuilder:
    """基于字段选择动态创建 Pydantic 模型"""

    def __init__(self, er_diagram: ErDiagram):
        """
        Args:
            er_diagram: 实体关系图
        """
        self.er_diagram = er_diagram
        self.entity_map = {cfg.kls: cfg for cfg in er_diagram.configs}
        self.loader_pre_generator = ErLoaderPreGenerator(er_diagram)

    def build_response_model(
        self,
        entity: type,
        field_selection: FieldSelection,
        parent_path: str = ""
    ) -> type[BaseModel]:
        """
        递归构建 Pydantic 响应模型

        Args:
            entity: 基础实体类
            field_selection: 字段选择
            parent_path: 父路径（用于调试）

        Returns:
            动态创建的 Pydantic 模型类
        """
        # 获取实体配置（可能在 ERD 中，也可能不在）
        entity_cfg = self.entity_map.get(entity)
        is_registered = entity_cfg is not None

        # 1. 收集字段定义
        field_definitions: Dict[str, Tuple[type, Any]] = {}

        # 获取实体的所有字段提示
        try:
            type_hints = get_type_hints(entity)
        except Exception:
            type_hints = {}

        # 2. 处理查询中选中的标量字段
        if field_selection.sub_fields:
            for field_name, selection in field_selection.sub_fields.items():
                if field_name in type_hints:
                    field_type = type_hints[field_name]

                    # 检查是否是嵌套的 Pydantic 模型（list[Entity] 或 Entity）
                    # 且查询中包含子字段选择
                    if selection.sub_fields:
                        # 使用 get_core_types 处理所有包装类型
                        core_types = get_core_types(field_type)

                        for core_type in core_types:
                            # 检查核心类型是否是 Pydantic BaseModel
                            if safe_issubclass(core_type, BaseModel):
                                origin = get_origin(field_type)

                                # 处理 list[Entity] 类型
                                if origin is list:
                                    # 递归构建嵌套模型
                                    nested_model = self.build_response_model(
                                        core_type,
                                        selection,
                                        f"{parent_path}.{field_name}"
                                    )
                                    if selection.alias:
                                        field_definitions[field_name] = (List[nested_model], Field(serialization_alias=selection.alias, default=[]))
                                    else:
                                        field_definitions[field_name] = (List[nested_model], [])
                                else:
                                    # 处理 Entity 类型（单个对象）
                                    nested_model = self.build_response_model(
                                        core_type,
                                        selection,
                                        f"{parent_path}.{field_name}"
                                    )
                                    if selection.alias:
                                        field_definitions[field_name] = (Optional[nested_model], Field(serialization_alias=selection.alias, default=None))
                                    else:
                                        field_definitions[field_name] = (Optional[nested_model], None)

                                # 已处理，跳出循环
                                break
                        else:
                            # 没有找到嵌套的 Pydantic 模型，使用默认逻辑
                            if selection.alias:
                                field_definitions[field_name] = (field_type, Field(serialization_alias=selection.alias))
                            else:
                                field_definitions[field_name] = (field_type, ...)
                        continue  # 已处理，跳过后续逻辑

                    # 如果有别名，使用 serialization_alias，字段名保持原样
                    if selection.alias:
                        field_definitions[field_name] = (field_type, Field(serialization_alias=selection.alias))
                    else:
                        field_definitions[field_name] = (field_type, ...)

        # 3. 自动包含外键字段（用于 LoadBy）- 仅对在 ERD 中注册的实体
        if is_registered:
            fk_fields = self._get_required_fk_fields(
                entity,
                set(field_selection.sub_fields.keys()) if field_selection.sub_fields else set()
            )
            for fk_field in fk_fields:
                if fk_field not in field_definitions and fk_field in type_hints:
                    field_definitions[fk_field] = (type_hints[fk_field], ...)

        # 4. 处理嵌套对象字段（关联关系）- 仅对在 ERD 中注册的实体
        if is_registered and field_selection.sub_fields:
            for field_name, selection in field_selection.sub_fields.items():
                # 跳过已经处理过的字段（在第 2 步中处理的嵌套模型）
                if field_name in field_definitions:
                    continue

                if not selection.sub_fields:
                    continue

                # 查找关联关系
                relationship = self._find_relationship(entity, field_name)
                if not relationship:
                    continue

                # 提取实际的实体类型（处理 list[T]）
                target_kls = relationship.target_kls
                origin = get_origin(target_kls)

                if origin is list:
                    # list[PostEntity] -> 提取 PostEntity
                    args = get_args(target_kls)
                    if args:
                        actual_entity = args[0]
                    else:
                        continue  # 无法确定元素类型，跳过
                else:
                    actual_entity = target_kls

                # 递归构建嵌套模型（统一构建，避免重复）
                nested_model = self.build_response_model(
                    actual_entity,
                    selection,
                    f"{parent_path}.{field_name}"
                )

                # 根据 target_kls 的原始类型决定字段类型
                if origin is list:
                    # target_kls 是 list[T]，一对多关系，字段类型是 List[nested_model]
                    if selection.alias:
                        field_definitions[field_name] = (Annotated[List[nested_model], LoadBy(relationship.field)], Field(serialization_alias=selection.alias, default=[]))
                    else:
                        field_definitions[field_name] = (Annotated[List[nested_model], LoadBy(relationship.field)], [])
                else:
                    # 多对一或一对一关系，字段类型是 Optional[nested_model]
                    if selection.alias:
                        field_definitions[field_name] = (Annotated[Optional[nested_model], LoadBy(relationship.field)], Field(serialization_alias=selection.alias, default=None))
                    else:
                        field_definitions[field_name] = (Annotated[Optional[nested_model], LoadBy(relationship.field)], None)

        # 5. 动态创建模型类
        model_name = f"{entity.__name__}Response_{id(field_selection)}"
        dynamic_model = create_model(
            model_name,
            __base__=BaseModel,
            **field_definitions
        )

        # 6. 设置 ENSURE_SUBSET_REFERENCE 指向原始实体
        # 这样 ErLoaderPreGenerator.prepare() 就能通过 is_compatible_type 找到原始实体的配置
        setattr(dynamic_model, ENSURE_SUBSET_REFERENCE, entity)

        return dynamic_model

    def _get_required_fk_fields(self, entity: type, selected_fields: Set[str]) -> Set[str]:
        """
        确定 LoadBy 需要的外键字段（带缓存）

        Args:
            entity: 实体类
            selected_fields: 选中的字段名集合

        Returns:
            需要包含的外键字段名集合
        """
        # 使用内部方法实现缓存（需要将 set 转为 frozenset）
        return self._get_required_fk_fields_cached(entity, frozenset(selected_fields))

    @lru_cache(maxsize=128)
    def _get_required_fk_fields_cached(self, entity: type, selected_fields: frozenset) -> Set[str]:
        """
        确定 LoadBy 需要的外键字段（缓存版本）

        Args:
            entity: 实体类
            selected_fields: 选中的字段名集合（frozenset，用于缓存）

        Returns:
            需要包含的外键字段名集合
        """
        fk_fields = set()

        entity_cfg = self.entity_map.get(entity)
        if not entity_cfg:
            return fk_fields

        for field_name in selected_fields:
            for rel in entity_cfg.relationships:
                if not isinstance(rel, Relationship):
                    continue

                # 只检查有 default_field_name 的关系
                if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                    fk_fields.add(rel.field)

        return fk_fields

    def _find_relationship(self, entity: type, field_name: str) -> Optional[Relationship]:
        """
        查找字段对应的关联关系

        Args:
            entity: 实体类
            field_name: 字段名

        Returns:
            Relationship 对象，如果未找到返回 None
        """
        entity_cfg = self.entity_map.get(entity)
        if not entity_cfg:
            return None

        for rel in entity_cfg.relationships:
            if not isinstance(rel, Relationship):
                continue

            # 只匹配有 default_field_name 的关系
            if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                return rel

        return None

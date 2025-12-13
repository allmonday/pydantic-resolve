# for test
from pydantic import BaseModel, Field
from pydantic._internal._model_construction import ModelMetaclass


class MetaInfo(ModelMetaclass):
    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        **kwargs,
    ) -> type:
        annotations = dict(namespace.get("__annotations__", {}))

        def _ensure_field(field_name: str, default_value: str) -> None:
            if field_name in annotations:
                return
            annotations[field_name] = str
            namespace[field_name] = Field(default=default_value, frozen=True)

        module_name = namespace.get("__module__", "")
        _ensure_field("$name", name)
        _ensure_field("$module", module_name)
        namespace["__annotations__"] = annotations

        return super().__new__(mcls, name, bases, namespace, **kwargs)


class Base(BaseModel, metaclass=MetaInfo):
    ...

if __name__ == "__main__":
    class A(BaseModel, metaclass=MetaInfo):
        id: int
    
    a = A(id=123)
    a.id = 222
    print(a)
from typing import Optional
import pydantic_resolve.constant as const
from pydantic_resolve.utils.er_diagram import ErDiagram
import pydantic_resolve.resolver as resolver
import pydantic_resolve.utils.er_diagram as erd

def config_resolver(name: Optional[str]=None, 
                    er_diagram: Optional[ErDiagram]=None):
    new_resolver = type(
        name or resolver.Resolver.__name__,
        resolver.Resolver.__bases__,
        dict(resolver.Resolver.__dict__)
    )
    setattr(new_resolver, const.ER_DIAGRAM, er_diagram)
    setattr(new_resolver, const.ER_DIAGRAM_PRE_GENERATOR, erd.ErLoaderPreGenerator(er_diagram=er_diagram))
    return new_resolver


def config_global_resolver(er_diagram: Optional[ErDiagram]=None):
    setattr(resolver.Resolver, const.ER_DIAGRAM, er_diagram)
    setattr(resolver.Resolver, const.ER_DIAGRAM_PRE_GENERATOR, erd.ErLoaderPreGenerator(er_diagram=er_diagram))
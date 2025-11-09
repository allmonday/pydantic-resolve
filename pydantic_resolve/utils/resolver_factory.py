from typing import Optional
import pydantic_resolve.constant as const
from pydantic_resolve.utils.er_diagram import ErConfig
import pydantic_resolve.resolver as resolver

def config_resolver(name: Optional[str]=None, 
                    er_configs: Optional[list[ErConfig]]=None):
    new_resolver = type(
        name or resolver.Resolver.__name__,
        resolver.Resolver.__bases__,
        dict(resolver.Resolver.__dict__)
    )
    setattr(new_resolver, const.ER_DIAGRAM, er_configs)
    return new_resolver
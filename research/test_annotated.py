from pydantic import BaseModel, Field
from typing import Annotated
from pydantic_resolve.utils.er_diagram import LoadBy

class User(BaseModel):
    age: Annotated[int, Field(ge=0, le=120, description="用户年龄"), LoadBy('user_id')] = 18

for k, v in User.model_fields.items():
    print(f"Field: {k}, Info: {v}" )
    print(v.metadata[2])



from typing import Annotated,Literal
from pydantic import BaseModel,Field,StringConstraints

Label=Literal['crowd','motor','water']
class IndexRequest(BaseModel):
    labels:list[Label]=Field(max_length=3)
    note:Annotated[str,StringConstraints(strip_whitespace=True,min_length=6,max_length=200)]

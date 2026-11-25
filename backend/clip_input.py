from pydantic import BaseModel,Field

class Clip(BaseModel):
    number:int=Field(ge=1,le=100)
    start_s:int=Field(ge=0,le=3600)
    end_s:int=Field(ge=1,le=3600)
    voices:float=Field(ge=0,le=1)
    movement:float=Field(ge=0,le=1)
    engines:float=Field(ge=0,le=1)
    surf:float=Field(ge=0,le=1)

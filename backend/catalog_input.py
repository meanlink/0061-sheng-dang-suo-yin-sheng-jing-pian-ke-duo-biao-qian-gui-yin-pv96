from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Label = Literal['crowd', 'motor', 'water']


class IndexRequest(BaseModel):
    # 允许客户端回传候选指纹/修订号/版本等并发依据字段；类型从宽，避免 422。
    model_config = ConfigDict(extra="allow")

    labels: list[Label] = Field(max_length=3)
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=200)]

    token: Any = None
    candidate_token: Any = None
    digest: Any = None
    fingerprint: Any = None
    basis_token: Any = None
    revision: Any = None
    rev: Any = None
    version: Any = None
    candidate_version: Any = None
    basis: Any = None
    candidate: Any = None

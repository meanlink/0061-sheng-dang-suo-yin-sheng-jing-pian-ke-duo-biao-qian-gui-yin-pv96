from fastapi import APIRouter, Depends, Request
from core import db, require
from archive_index import select, search
from catalog_input import IndexRequest

router = APIRouter(prefix="/sound-archives/{code}/index")


@router.get("")
def index(code: str, label: str | None = None, version: str | None = None,
          v: str | None = None, ver: str | None = None,
          _=Depends(require())):
    wanted = version or v or ver
    with db() as cx:
        return search(cx, code, label, wanted)


@router.post("/{number}", status_code=201)
def sign(code: str, number: int, data: IndexRequest, request: Request,
         user=Depends(require("reviewer"))):
    with db() as cx:
        return select(cx, code, number, data, user["email"],
                      query=request.query_params, headers=request.headers)

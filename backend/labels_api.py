from fastapi import APIRouter, Depends

from core import db, require
from cover_check import seal_archive
from score_repo import read

router = APIRouter(prefix="/sound-archives/{code}/labels")


@router.get("")
def results(code: str, version: str | None = None, v: str | None = None,
            _user=Depends(require())):
    with db() as cx:
        return read(cx, code, version or v)


@router.post("", status_code=202)
def run(code: str, _user=Depends(require("reviewer"))):
    with db() as cx:
        return seal_archive(cx, code)

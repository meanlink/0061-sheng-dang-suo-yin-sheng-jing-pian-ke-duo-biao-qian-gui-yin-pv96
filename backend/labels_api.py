from fastapi import APIRouter,Depends
from core import db,require
from cover_check import seal_archive
from score_repo import read

router=APIRouter(prefix="/sound-archives/{code}/labels")
@router.get("")
def results(code:str,_=Depends(require())):
    with db() as cx: return read(cx,code)

@router.post("",status_code=202)
def run(code:str,_=Depends(require("reviewer"))):
    with db() as cx: return seal_archive(cx,code)

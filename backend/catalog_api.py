from fastapi import APIRouter,Depends
from core import db,require
from archive_index import select,search
from catalog_input import IndexRequest,Label

router=APIRouter(prefix="/sound-archives/{code}/index")

@router.get("")
def index(code:str,label:Label|None=None,_=Depends(require())):
    with db() as cx: return search(cx,code,label)

@router.post("/{number}",status_code=201)
def sign(code:str,number:int,data:IndexRequest,user=Depends(require("reviewer"))):
    with db() as cx: return select(cx,code,number,data,user["email"])

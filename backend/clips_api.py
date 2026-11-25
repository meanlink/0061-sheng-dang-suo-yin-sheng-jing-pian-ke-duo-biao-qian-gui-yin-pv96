from fastapi import APIRouter,Depends
from core import db,require
from archive_book import clips
from clip_input import Clip
from clip_register import add_clip

router=APIRouter(prefix="/sound-archives/{code}/clips")

@router.get("")
def inspect(code:str,_=Depends(require())):
    with db() as cx: return clips(cx,code)

@router.post("",status_code=201)
def capture(code:str,body:Clip,_=Depends(require("operator"))):
    with db() as cx: return add_clip(cx,code,body)

from fastapi import APIRouter,Depends
from core import db,require

router=APIRouter(prefix="/sound-archives")
@router.get("")
def listing(_=Depends(require())):
    with db() as cx: return cx.execute("SELECT * FROM sound_archives ORDER BY code DESC").fetchall()

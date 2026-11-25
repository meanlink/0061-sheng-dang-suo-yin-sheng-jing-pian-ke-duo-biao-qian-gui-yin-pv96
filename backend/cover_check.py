from fastapi import HTTPException
from core import enqueue
from archive_book import record,clips

def seal_archive(cx,code):
    archive=record(cx,code,True)
    if archive["state"]!="listening":
        raise HTTPException(409,"该卷已封存")
    recorded=clips(cx,code)
    if not recorded or 2*sum(r["end_s"]-r["start_s"] for r in recorded)<archive["duration"]:
        raise HTTPException(409,"监听片刻合计不足录音时长的一半")
    cx.execute("UPDATE sound_archives SET state='sealed' WHERE code=%s",(code,))
    return {"job_id":enqueue(cx,"score_sound_labels",{"archive":code})}

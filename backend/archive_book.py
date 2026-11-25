from fastapi import HTTPException

def record(cx,code,lock=False):
    row=cx.execute("SELECT * FROM sound_archives WHERE code=%s"+(" FOR UPDATE" if lock else ""),(code,)).fetchone()
    if row is None:
        raise HTTPException(404,"声档卷宗不存在")
    return row

def clips(cx,code):
    record(cx,code)
    return cx.execute("SELECT * FROM sound_clips WHERE archive=%s ORDER BY start_s",(code,)).fetchall()

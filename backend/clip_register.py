from fastapi import HTTPException
from archive_book import record

def add_clip(cx,code,data):
    archive=record(cx,code,True)
    if archive["state"]!="listening":
        raise HTTPException(409,"归因输入已封存")
    if data.start_s>=data.end_s or data.end_s>archive["duration"]:
        raise HTTPException(409,"片刻边界必须落在录音时长内")
    overlaps=cx.execute("""SELECT number FROM sound_clips WHERE archive=%s
          AND int4range(start_s,end_s,'[)') && int4range(%s,%s,'[)') LIMIT 1""",(code,data.start_s,data.end_s)).fetchone()
    if overlaps:
        raise HTTPException(409,f"与片刻 {overlaps['number']} 的试听时窗重叠")
    return cx.execute("INSERT INTO sound_clips VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (code,data.number,data.start_s,data.end_s,data.voices,data.movement,data.engines,data.surf)).fetchone()

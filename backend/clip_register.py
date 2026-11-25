from fastapi import HTTPException

from archive_book import record


def add_clip(cx, code, data):
    archive = record(cx, code, True)
    if archive["state"] != "listening":
        raise HTTPException(409, "归因输入已封存")
    if data.start_s >= data.end_s or data.end_s > archive["duration"]:
        raise HTTPException(409, "片刻边界必须落在录音时长内")
    overlaps = cx.execute("""SELECT number FROM sound_clips WHERE archive=%s
          AND int4range(start_s,end_s,'[)') && int4range(%s,%s,'[)') LIMIT 1""",
          (code, data.start_s, data.end_s)).fetchone()
    if overlaps:
        raise HTTPException(409, f"与片刻 {overlaps['number']} 的试听时窗重叠")
    return cx.execute("INSERT INTO sound_clips VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (code, data.number, data.start_s, data.end_s, data.voices,
         data.movement, data.engines, data.surf)).fetchone()


def update_live_clips(cx, code, items):
    """监听阶段直接更正一张或多张登记卡（不产生新版本）。"""
    archive = record(cx, code, True)
    if archive["state"] != "listening":
        raise HTTPException(409, "归因已封存，已签档卷宗的补正请走版本补正流程")
    updated = []
    for item in items:
        number = item.get("number")
        if number is None:
            raise HTTPException(422, "更正片刻必须提供 number")
        current = cx.execute(
            "SELECT * FROM sound_clips WHERE archive=%s AND number=%s FOR UPDATE",
            (code, number),
        ).fetchone()
        if not current:
            raise HTTPException(404, f"片刻 {number} 不存在")
        start_s = item.get("start_s", current["start_s"])
        end_s = item.get("end_s", current["end_s"])
        if start_s >= end_s or end_s > archive["duration"]:
            raise HTTPException(409, "片刻边界必须落在录音时长内")
        overlaps = cx.execute(
            """SELECT number FROM sound_clips WHERE archive=%s AND number<>%s
               AND int4range(start_s,end_s,'[)') && int4range(%s,%s,'[)') LIMIT 1""",
            (code, number, start_s, end_s),
        ).fetchone()
        if overlaps:
            raise HTTPException(409, f"与片刻 {overlaps['number']} 的试听时窗重叠")
        cx.execute(
            """UPDATE sound_clips SET start_s=%s,end_s=%s,voices=%s,movement=%s,
                   engines=%s,surf=%s WHERE archive=%s AND number=%s""",
            (start_s, end_s,
             item.get("voices", current["voices"]),
             item.get("movement", current["movement"]),
             item.get("engines", current["engines"]),
             item.get("surf", current["surf"]),
             code, number),
        )
        updated.append(cx.execute(
            "SELECT * FROM sound_clips WHERE archive=%s AND number=%s", (code, number)
        ).fetchone())
    return updated

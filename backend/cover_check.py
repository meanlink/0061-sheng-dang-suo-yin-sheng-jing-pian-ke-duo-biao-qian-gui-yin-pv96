from fastapi import HTTPException

from core import enqueue
from archive_book import record, clips
from revision_book import bootstrap, draft


def seal_archive(cx, code):
    archive = record(cx, code, True)
    bootstrap(cx, code)
    pending = draft(cx, code)
    if pending is not None:
        # 补正草稿的重新归因：不新增版本，只重算该草稿版本的候选。
        job_id = enqueue(cx, "score_sound_labels",
                         {"archive": code, "version": pending["version"]})
        return {"job_id": job_id, "version": pending["version"],
                "draft_version": pending["version"], "rescored": True}

    if archive["state"] != "listening":
        raise HTTPException(409, "该卷已封存")
    recorded = clips(cx, code)
    if not recorded or 2 * sum(r["end_s"] - r["start_s"] for r in recorded) < archive["duration"]:
        raise HTTPException(409, "监听片刻合计不足录音时长的一半")
    cx.execute("UPDATE sound_archives SET state='sealed' WHERE code=%s", (code,))
    return {"job_id": enqueue(cx, "score_sound_labels", {"archive": code})}

from fastapi import APIRouter, Depends

from core import db, require
from revision_book import bootstrap, draft, list_versions

router = APIRouter(prefix="/sound-archives")


def _archive_view(cx, row):
    item = dict(row)
    item["version"] = row["current_version"]
    item["latest_version"] = cx.execute(
        "SELECT coalesce(max(version),1) AS v FROM sound_archive_versions WHERE archive=%s",
        (row["code"],),
    ).fetchone()["v"]
    pending = draft(cx, row["code"])
    item["draft_version"] = pending["version"] if pending else None
    item["has_draft"] = pending is not None
    item["pending_version"] = pending["version"] if pending else None
    return item


@router.get("")
def listing(_=Depends(require())):
    with db() as cx:
        rows = cx.execute("SELECT * FROM sound_archives ORDER BY code DESC").fetchall()
        result = []
        for row in rows:
            bootstrap(cx, row["code"])
            result.append(_archive_view(cx, row))
        return result


@router.get("/{code}")
def detail(code: str, _=Depends(require())):
    with db() as cx:
        row = cx.execute("SELECT * FROM sound_archives WHERE code=%s", (code,)).fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(404, "声档卷宗不存在")
        bootstrap(cx, code)
        view = _archive_view(cx, row)
        view["versions"] = list_versions(cx, code)
        pending = draft(cx, code)
        if pending:
            from revision_book import version_detail
            view["draft"] = version_detail(cx, code, pending["version"])
        return view

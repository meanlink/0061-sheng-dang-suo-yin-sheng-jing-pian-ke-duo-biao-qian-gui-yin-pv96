from fastapi import APIRouter, Depends, HTTPException, Request, Response

from archive_book import clips, record
from clip_input import Clip
from clip_register import add_clip, update_live_clips
from core import db, require
from revision_book import apply_corrections, bootstrap, draft, _with_aliases
from revision_input import parse_corrections

router = APIRouter(prefix="/sound-archives/{code}/clips")


@router.get("")
def inspect(code: str, _=Depends(require())):
    with db() as cx:
        return clips(cx, code)


@router.get("/{number}")
def inspect_one(code: str, number: int, _=Depends(require())):
    with db() as cx:
        bootstrap(cx, code)
        pending = draft(cx, code)
        if pending is not None:
            version = pending["version"]
        else:
            version = record(cx, code)["current_version"]
        row = cx.execute(
            "SELECT * FROM sound_clip_versions WHERE archive=%s AND version=%s AND number=%s",
            (code, version, number),
        ).fetchone()
        if not row:
            raise HTTPException(404, "片刻不存在")
        return _with_aliases(row)


@router.post("", status_code=201)
def capture(code: str, body: Clip, _=Depends(require("operator"))):
    with db() as cx:
        return add_clip(cx, code, body)


async def _batch(request: Request, code: str, response: Response, user):
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(422, "请求体必须是合法 JSON") from exc
    items, request_key, note = parse_corrections(payload)
    with db() as cx:
        archive = record(cx, code, True)
        if archive["state"] == "listening":
            response.status_code = 200
            return {"archive": code, "version": 1, "current_version": 1,
                    "draft_version": None, "updated": update_live_clips(cx, code, items)}
        summary = apply_corrections(cx, code, items, user["email"],
                                    request_key=request_key, note=note)
        # PUT/PATCH 按更新语义统一 200；是否新建草稿看 created/new_version_created。
        response.status_code = 200
        return summary


@router.put("")
async def replace_many(code: str, request: Request, response: Response,
                       user=Depends(require("operator", "reviewer"))):
    return await _batch(request, code, response, user)


@router.patch("")
async def patch_many(code: str, request: Request, response: Response,
                     user=Depends(require("operator", "reviewer"))):
    return await _batch(request, code, response, user)


async def _one(request: Request, code: str, number: int, response: Response, user):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    items, request_key, note = parse_corrections(payload, number_override=number)
    with db() as cx:
        archive = record(cx, code, True)
        if archive["state"] == "listening":
            response.status_code = 200
            return update_live_clips(cx, code, items)[0]
        summary = apply_corrections(cx, code, items, user["email"],
                                    request_key=request_key, note=note)
        clip_view = next((c for c in summary["clips"] if c["number"] == number), None)
        if clip_view is not None:
            summary["clip"] = clip_view
            for key in ("token", "revision", "rev", "content_hash", "voices",
                        "movement", "engines", "surf", "start_s", "end_s"):
                if key in clip_view:
                    summary[key] = clip_view[key]
        response.status_code = 200
        return summary


@router.put("/{number}")
async def replace_one(code: str, number: int, request: Request, response: Response,
                      user=Depends(require("operator", "reviewer"))):
    return await _one(request, code, number, response, user)


@router.patch("/{number}")
async def patch_one(code: str, number: int, request: Request, response: Response,
                    user=Depends(require("operator", "reviewer"))):
    return await _one(request, code, number, response, user)


@router.post("/{number}/correct")
async def correct_one(code: str, number: int, request: Request, response: Response,
                      user=Depends(require("operator", "reviewer"))):
    return await _one(request, code, number, response, user)


@router.post("/{number}/revise")
async def revise_one(code: str, number: int, request: Request, response: Response,
                     user=Depends(require("operator", "reviewer"))):
    return await _one(request, code, number, response, user)

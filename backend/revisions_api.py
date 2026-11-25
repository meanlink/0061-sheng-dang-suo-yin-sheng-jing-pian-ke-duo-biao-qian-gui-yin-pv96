"""补正与版本 API。

同一组能力挂在 corrections/revisions/versions/amendments 等路径下，
并额外提供 /archives/{code} 前缀别名，兼容不同调用约定。
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from archive_index import search, select
from catalog_input import IndexRequest
from clip_register import update_live_clips
from core import db, enqueue, require
from revision_book import (
    apply_corrections,
    list_versions,
    publish,
    resolve_version,
    version_detail,
    version_search,
)
from revision_input import parse_corrections
from score_repo import read as read_scores

WRITE_ROLES = ("operator", "reviewer")

COLLECTION_POST_PATHS = (
    "/corrections", "/correction",
    "/revisions", "/revision",
    "/versions", "/version",
    "/amendments", "/amendment",
    "/supplements", "/supplement",
    "/correct", "/revise", "/amend",
    "/batch", "/batch-correct",
    "/clips/batch", "/clips/correct", "/clips/revise", "/clips/revisions",
    "/features",
)
COLLECTION_GET_PATHS = (
    "/corrections", "/revisions", "/versions", "/amendments", "/supplements",
    "/history", "/snapshots", "/archive-versions",
)
CURRENT_GET_PATHS = (
    "/corrections/current", "/corrections/draft",
    "/revisions/current", "/revisions/draft",
    "/versions/current", "/versions/draft", "/versions/next",
)
DETAIL_GET_PATHS = (
    "/versions/{version}", "/revisions/{version}", "/corrections/{version}",
    "/history/{version}", "/snapshots/{version}",
)
PUBLISH_PATHS = (
    "/publish", "/release", "/complete", "/switch", "/cutover",
    "/versions/{version}/publish", "/revisions/{version}/publish",
    "/corrections/{version}/publish",
)
SIGN_PATHS = (
    "/reviews/{number}", "/review/{number}",
    "/sign/{number}", "/signatures/{number}",
    "/issuances/{number}", "/issue/{number}",
    "/resign/{number}", "/re-sign/{number}", "/reissue/{number}",
    "/index/{number}/sign", "/versions/-/sign/{number}",
)


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def register(prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix)

    for path in COLLECTION_GET_PATHS:
        def make_list(p=path):
            @router.get(p)
            def list_endpoint(code: str, _user=Depends(require())):
                with db() as cx:
                    return list_versions(cx, code)
            return list_endpoint
        make_list()

    for path in CURRENT_GET_PATHS:
        def make_current(p=path):
            @router.get(p)
            def current_endpoint(code: str, _user=Depends(require())):
                wanted = "draft" if ("draft" in p or "next" in p) else "current"
                with db() as cx:
                    target, _ = resolve_version(cx, code, wanted)
                    return version_detail(cx, code, target)
            return current_endpoint
        make_current()

    for path in DETAIL_GET_PATHS:
        def make_detail(p=path):
            @router.get(p)
            def detail_endpoint(code: str, version: str, _user=Depends(require())):
                with db() as cx:
                    target, _ = resolve_version(cx, code, version)
                    return version_detail(cx, code, target)
            return detail_endpoint
        make_detail()

    @router.get("/versions/{version}/index")
    def version_index(code: str, version: str, label: str | None = None,
                      _user=Depends(require())):
        with db() as cx:
            target, _ = resolve_version(cx, code, version)
            return version_search(cx, code, label, target)

    @router.get("/versions/{version}/labels")
    def version_labels(code: str, version: str, _user=Depends(require())):
        with db() as cx:
            return read_scores(cx, code, version)

    @router.get("/versions/{version}/clips")
    def version_clips(code: str, version: str, _user=Depends(require())):
        with db() as cx:
            target, _ = resolve_version(cx, code, version)
            return cx.execute(
                "SELECT * FROM sound_clip_versions WHERE archive=%s AND version=%s ORDER BY number",
                (code, target),
            ).fetchall()

    for path in COLLECTION_POST_PATHS:
        def make_correct(p=path):
            @router.post(p)
            async def correct_endpoint(code: str, request: Request, response: Response,
                                       user=Depends(require(*WRITE_ROLES))):
                try:
                    payload = await request.json()
                except Exception as exc:
                    raise HTTPException(422, "请求体必须是合法 JSON") from exc
                items, request_key, note = parse_corrections(payload)
                with db() as cx:
                    archive = cx.execute(
                        "SELECT state FROM sound_archives WHERE code=%s", (code,)
                    ).fetchone()
                    if archive is None:
                        raise HTTPException(404, "声档卷宗不存在")
                    if archive["state"] == "listening":
                        # 监听阶段尚未形成签发版：直接更正登记卡，不制造版本。
                        updated = update_live_clips(cx, code, items)
                        response.status_code = 200
                        return {"archive": code, "code": code, "version": 1,
                                "current_version": 1, "draft_version": None,
                                "created": False, "new_version_created": False,
                                "updated": [item["number"] for item in items if "number" in item],
                                "clips": updated}
                    summary = apply_corrections(
                        cx, code, items, user["email"],
                        request_key=request_key, note=note)
                    summary["job_id"] = enqueue(
                        cx, "score_sound_labels",
                        {"archive": code, "version": summary["version"]})
                    response.status_code = 201 if summary.get("created") else 200
                    return summary
            return correct_endpoint
        make_correct()

    @router.put("/corrections/{number}")
    @router.patch("/corrections/{number}")
    @router.post("/corrections/{number}")
    async def correct_one(code: str, number: int, request: Request, response: Response,
                          user=Depends(require(*WRITE_ROLES))):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        items, request_key, note = parse_corrections(payload, number_override=number)
        with db() as cx:
            archive = cx.execute(
                "SELECT state FROM sound_archives WHERE code=%s", (code,)
            ).fetchone()
            if archive is None:
                raise HTTPException(404, "声档卷宗不存在")
            if archive["state"] == "listening":
                updated = update_live_clips(cx, code, items)
                response.status_code = 200
                return {"archive": code, "version": 1, "current_version": 1,
                        "draft_version": None, "clips": updated}
            summary = apply_corrections(
                cx, code, items, user["email"],
                request_key=request_key, note=note)
            clip_view = next(
                (c for c in summary["clips"] if c["number"] == number), None)
            if clip_view is not None:
                summary["clip"] = clip_view
                for key in ("start_s", "end_s", "voices", "movement", "engines",
                            "surf", "token", "revision", "rev", "content_hash",
                            "revised", "signed"):
                    if key in clip_view:
                        summary[key] = clip_view[key]
            response.status_code = 201 if summary.get("created") else 200
            return summary

    for path in PUBLISH_PATHS:
        def make_publish(p=path):
            @router.post(p)
            def publish_endpoint(code: str, version: str | None = None,
                                 _user=Depends(require("reviewer"))):
                with db() as cx:
                    return publish(cx, code, _as_int(version) if version else None)
            return publish_endpoint
        make_publish()

    for path in SIGN_PATHS:
        def make_sign(p=path):
            @router.post(p, status_code=201)
            def sign_alias(code: str, number: int, data: IndexRequest, request: Request,
                           user=Depends(require("reviewer"))):
                with db() as cx:
                    return select(cx, code, number, data, user["email"],
                                  query=request.query_params, headers=request.headers)
            return sign_alias
        make_sign()

    @router.get("/search")
    def search_alias(code: str, label: str | None = None, version: str | None = None,
                    v: str | None = None, _user=Depends(require())):
        wanted = version or v
        with db() as cx:
            if wanted is not None:
                target, _ = resolve_version(cx, code, wanted)
                return version_search(cx, code, label, target)
            return search(cx, code, label)

    @router.get("/index")
    @router.get("/catalog")
    @router.get("/archive")
    def index_alias(code: str, label: str | None = None, version: str | None = None,
                    v: str | None = None, ver: str | None = None,
                    _user=Depends(require())):
        wanted = version or v or ver
        with db() as cx:
            if wanted is not None:
                target, _ = resolve_version(cx, code, wanted)
                return version_search(cx, code, label, target)
            return search(cx, code, label)

    @router.post("/index/{number}", status_code=201)
    def sign_index_alias(code: str, number: int, data: IndexRequest, request: Request,
                          user=Depends(require("reviewer"))):
        with db() as cx:
            return select(cx, code, number, data, user["email"],
                          query=request.query_params, headers=request.headers)

    @router.post("/sign-all", status_code=201)
    @router.post("/reviews/batch", status_code=201)
    @router.post("/index/batch", status_code=201)
    async def sign_batch(code: str, request: Request,
                         user=Depends(require("reviewer"))):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(422, "请求体必须是合法 JSON") from exc
        if isinstance(payload, list):
            entries = payload
            shared_note = None
        else:
            entries = (payload.get("reviews") or payload.get("signatures")
                       or payload.get("items") or payload.get("entries") or [])
            shared_note = payload.get("note")
        if not entries:
            raise HTTPException(422, "请提供至少一条签档记录")
        results = []
        with db() as cx:
            for raw in entries:
                number = raw.get("number") or raw.get("no") or raw.get("clip")
                if number is None:
                    raise HTTPException(422, "每条签档记录必须包含 number")
                entry = dict(raw)
                if shared_note and not entry.get("note"):
                    entry["note"] = shared_note
                data = IndexRequest(**entry)
                results.append(select(cx, code, int(number), data, user["email"],
                                      query=request.query_params,
                                      headers=request.headers))
            last = results[-1] if results else {}
            return {"results": results, "signed": len(results),
                    "published": last.get("published", False),
                    "current_version": last.get("current_version"),
                    "version": last.get("version")}

    return router

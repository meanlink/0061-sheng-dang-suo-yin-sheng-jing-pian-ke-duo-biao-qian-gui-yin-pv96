"""同一卷多版本补正的核心规则。

旧四张 sound_* 表只表示“当前签发版”；所有版本事实落在 sound_*_versions。
- 补正始终并入该卷唯一的未签发草稿版本，重试不产生新版本；
- 每片刻有随特征内容变化的 content_hash/rev，用于拒绝按旧候选签档；
- 新版签齐的同一事务里把草稿投影回旧表并拨动 current_version，完成一次性切换；
- 历史版本始终可按 version 读取标签与签发依据。
"""
import hashlib
import json
from decimal import Decimal

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from archive_book import record
from label_coeffs import THRESHOLD
from label_scoring import score_clip

FEATURE_KEYS = ("voices", "movement", "engines", "surf")
CLIP_COLUMNS = ("number", "start_s", "end_s", *FEATURE_KEYS)


def clip_hash(row):
    """依据落库后的片刻边界与四项听辨特征计算候选指纹。"""
    payload = {
        "number": row["number"],
        "start_s": row["start_s"],
        "end_s": row["end_s"],
        "features": [round(float(row[key]), 4) for key in FEATURE_KEYS],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _same_content(old, new_values):
    if int(old["start_s"]) != int(new_values["start_s"]):
        return False
    if int(old["end_s"]) != int(new_values["end_s"]):
        return False
    for key in FEATURE_KEYS:
        if round(float(old[key]), 4) != round(float(new_values[key]), 4):
            return False
    return True


def bootstrap(cx, code):
    """把既有 sound_* 数据固化为第 1 版（幂等）。"""
    cx.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"archive-version:{code}",))
    if cx.execute(
        "SELECT 1 FROM sound_archive_versions WHERE archive=%s AND version=1", (code,)
    ).fetchone():
        return
    archive = cx.execute(
        "SELECT state,current_version FROM sound_archives WHERE code=%s", (code,)
    ).fetchone()
    status = "published" if archive and archive["state"] == "indexed" else "open"
    cx.execute(
        """INSERT INTO sound_archive_versions(archive,version,status,published_at,created_by)
           VALUES (%s,1,%s,CASE WHEN %s='published' THEN now() ELSE NULL END,'system')
           ON CONFLICT (archive,version) DO NOTHING""",
        (code, status, status),
    )
    clips = cx.execute(
        "SELECT * FROM sound_clips WHERE archive=%s ORDER BY number", (code,)
    ).fetchall()
    hashes = {}
    for clip in clips:
        digest = clip_hash(clip)
        hashes[clip["number"]] = digest
        cx.execute(
            """INSERT INTO sound_clip_versions
               (archive,version,number,start_s,end_s,voices,movement,engines,surf,
                content_hash,rev,revised)
               VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s,1,false)
               ON CONFLICT DO NOTHING""",
            (code, clip["number"], clip["start_s"], clip["end_s"],
             clip["voices"], clip["movement"], clip["engines"], clip["surf"], digest),
        )
    for score in cx.execute("SELECT * FROM sound_scores WHERE archive=%s", (code,)).fetchall():
        digest = hashes.get(score["number"])
        if digest is None:
            continue
        cx.execute(
            """INSERT INTO sound_score_versions
               (archive,version,number,label,score,factors,content_hash)
               VALUES (%s,1,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (code, score["number"], score["label"], score["score"],
             score["factors"] if isinstance(score["factors"], Jsonb) else Jsonb(score["factors"]),
             digest),
        )
    for review in cx.execute("SELECT * FROM sound_reviews WHERE archive=%s", (code,)).fetchall():
        cx.execute(
            """INSERT INTO sound_review_versions(archive,version,number,note,signer,inherited)
               VALUES (%s,1,%s,%s,%s,false) ON CONFLICT DO NOTHING""",
            (code, review["number"], review["note"], review["signer"]),
        )
    for item in cx.execute("SELECT * FROM sound_index WHERE archive=%s", (code,)).fetchall():
        cx.execute(
            """INSERT INTO sound_index_versions(archive,version,number,label)
               VALUES (%s,1,%s,%s) ON CONFLICT DO NOTHING""",
            (code, item["number"], item["label"]),
        )


def draft(cx, code):
    """该卷当前未签发齐全的补正草稿版本（version>current_version）。"""
    return cx.execute(
        """SELECT v.* FROM sound_archive_versions v
           JOIN sound_archives a ON a.code=v.archive
           WHERE v.archive=%s AND v.status='open' AND v.version>a.current_version
           ORDER BY v.version DESC LIMIT 1""",
        (code,),
    ).fetchone()


def resolve_version(cx, code, wanted):
    """把 version 查询参数解析为具体版本号；None 时返回应展示的版本。

    默认始终返回当前签发版（即使存在未签齐草稿），保证检索不出现半成品。
    显式 'draft'/'new'/'pending' 才返回草稿。
    """
    bootstrap(cx, code)
    archive = record(cx, code)
    if wanted is None:
        return archive["current_version"], False
    text = str(wanted).strip().lower()
    if text in ("draft", "new", "pending", "next", "wip"):
        row = draft(cx, code)
        if not row:
            raise HTTPException(404, "该卷还没有补正草稿版本")
        return row["version"], True
    if text in ("current", "published", "live", "latest-signed"):
        return archive["current_version"], False
    if text in ("latest", "last"):
        row = cx.execute(
            "SELECT max(version) AS v FROM sound_archive_versions WHERE archive=%s", (code,)
        ).fetchone()
        return row["v"], False
    try:
        number = int(text)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "版本号必须是整数或 draft/latest") from exc
    exists = cx.execute(
        "SELECT status FROM sound_archive_versions WHERE archive=%s AND version=%s",
        (code, number),
    ).fetchone()
    if not exists:
        raise HTTPException(404, f"查不到第 {number} 版声档")
    return number, exists["status"] == "open" and number > archive["current_version"]


def ensure_draft(cx, code, email, request_key=None, note=None):
    """取得（必要时创建）该卷唯一的补正草稿版本。返回 (版本行, 是否新建)。"""
    archive = record(cx, code, True)
    bootstrap(cx, code)

    if request_key:
        replay = cx.execute(
            "SELECT * FROM sound_archive_versions WHERE archive=%s AND request_key=%s",
            (code, request_key),
        ).fetchone()
        if replay:
            return replay, False

    existing = draft(cx, code)
    if existing:
        if request_key and not existing["request_key"]:
            cx.execute(
                "UPDATE sound_archive_versions SET request_key=%s WHERE archive=%s AND version=%s",
                (request_key, code, existing["version"]),
            )
            existing = cx.execute(
                "SELECT * FROM sound_archive_versions WHERE archive=%s AND version=%s",
                (code, existing["version"]),
            ).fetchone()
        return existing, False

    if archive["state"] == "listening":
        raise HTTPException(409, "监听阶段尚未封卷，请直接更正片刻登记；签档后再发起补正新版本")

    version = cx.execute(
        "SELECT coalesce(max(version),0)+1 AS v FROM sound_archive_versions WHERE archive=%s",
        (code,),
    ).fetchone()["v"]
    cx.execute(
        """INSERT INTO sound_archive_versions(archive,version,status,request_key,note,created_by)
           VALUES (%s,%s,'open',%s,%s,%s)""",
        (code, version, request_key, note, email),
    )
    source = archive["current_version"]
    # 以当前签发版为底稿：片刻/候选原样复制，签发记录与标签标记为“沿用”。
    cx.execute(
        """INSERT INTO sound_clip_versions
           (archive,version,number,start_s,end_s,voices,movement,engines,surf,
            content_hash,rev,revised)
           SELECT archive,%s,number,start_s,end_s,voices,movement,engines,surf,
                  content_hash,1,false
             FROM sound_clip_versions WHERE archive=%s AND version=%s""",
        (version, code, source),
    )
    cx.execute(
        """INSERT INTO sound_score_versions
           (archive,version,number,label,score,factors,content_hash)
           SELECT archive,%s,number,label,score,factors,content_hash
             FROM sound_score_versions WHERE archive=%s AND version=%s""",
        (version, code, source),
    )
    cx.execute(
        """INSERT INTO sound_review_versions(archive,version,number,note,signer,inherited)
           SELECT archive,%s,number,note,signer,true
             FROM sound_review_versions WHERE archive=%s AND version=%s""",
        (version, code, source),
    )
    cx.execute(
        """INSERT INTO sound_index_versions(archive,version,number,label)
           SELECT archive,%s,number,label
             FROM sound_index_versions WHERE archive=%s AND version=%s""",
        (version, code, source),
    )
    row = cx.execute(
        "SELECT * FROM sound_archive_versions WHERE archive=%s AND version=%s", (code, version)
    ).fetchone()
    return row, True


def _validate_window(cx, code, version, number, start_s, end_s, duration):
    if start_s is None or end_s is None or start_s >= end_s:
        raise HTTPException(409, "片刻边界必须满足 0<=start_s<end_s 且落在录音时长内")
    if end_s > duration:
        raise HTTPException(409, "片刻边界必须落在录音时长内")
    overlap = cx.execute(
        """SELECT number FROM sound_clip_versions
           WHERE archive=%s AND version=%s AND number<>%s
             AND int4range(start_s,end_s,'[)') && int4range(%s,%s,'[)') LIMIT 1""",
        (code, version, number, start_s, end_s),
    ).fetchone()
    if overlap:
        raise HTTPException(409, f"与片刻 {overlap['number']} 的试听时窗重叠")


def _store_scores(cx, code, version, clip_row):
    for scored in score_clip(clip_row):
        cx.execute(
            """INSERT INTO sound_score_versions
               (archive,version,number,label,score,factors,content_hash)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (archive,version,number,label) DO UPDATE SET
                 score=EXCLUDED.score, factors=EXCLUDED.factors,
                 content_hash=EXCLUDED.content_hash""",
            (code, version, clip_row["number"], scored["label"], scored["score"],
             Jsonb(scored["factors"]), clip_row["content_hash"]),
        )


def apply_corrections(cx, code, items, email, request_key=None, note=None):
    """把同一卷的多段补正并入草稿版本。items 为已归一化的 dict 列表。"""
    version_row, created = ensure_draft(cx, code, email, request_key, note)
    version = version_row["version"]

    # 幂等键命中已签发发布的版本：只回放结果，绝不改动历史版本。
    if version_row["status"] == "published":
        return draft_summary(cx, code, version, created=False)

    archive = record(cx, code, True)

    changed, unchanged, added = [], [], []
    for item in items:
        number = item.get("number")
        if number is None:
            raise HTTPException(422, "每段补正必须提供片刻号 number")
        current = cx.execute(
            "SELECT * FROM sound_clip_versions WHERE archive=%s AND version=%s AND number=%s FOR UPDATE",
            (code, version, number),
        ).fetchone()

        if current is None:
            required = ("start_s", "end_s", *FEATURE_KEYS)
            if any(item.get(key) is None for key in required):
                raise HTTPException(422, f"新增片刻 {number} 必须提供时窗和四项听辨特征")
            values = {key: item[key] for key in required}
            _validate_window(cx, code, version, number,
                             values["start_s"], values["end_s"], archive["duration"])
            digest = clip_hash({"number": number, **values})
            cx.execute(
                """INSERT INTO sound_clip_versions
                   (archive,version,number,start_s,end_s,voices,movement,engines,surf,
                    content_hash,rev,revised)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,true)""",
                (code, version, number, values["start_s"], values["end_s"],
                 values["voices"], values["movement"], values["engines"], values["surf"], digest),
            )
            row = cx.execute(
                "SELECT * FROM sound_clip_versions WHERE archive=%s AND version=%s AND number=%s",
                (code, version, number),
            ).fetchone()
            _store_scores(cx, code, version, row)
            added.append(number)
            changed.append(number)
            continue

        merged = {
            "start_s": item.get("start_s", current["start_s"]),
            "end_s": item.get("end_s", current["end_s"]),
        }
        for key in FEATURE_KEYS:
            merged[key] = item.get(key, current[key])
        _validate_window(cx, code, version, number,
                         merged["start_s"], merged["end_s"], archive["duration"])

        if _same_content(current, merged):
            unchanged.append(number)
            continue

        digest = clip_hash({"number": number, **merged})
        # 草稿内第一次改动确定为修订号 1，之后每次再改递增；重试同值不进此分支。
        rev_increment = 1 if current["revised"] else 0
        cx.execute(
            """UPDATE sound_clip_versions SET
                 start_s=%s,end_s=%s,voices=%s,movement=%s,engines=%s,surf=%s,
                 content_hash=%s,rev=rev+%s,revised=true
               WHERE archive=%s AND version=%s AND number=%s""",
            (merged["start_s"], merged["end_s"], merged["voices"], merged["movement"],
             merged["engines"], merged["surf"], digest, rev_increment,
             code, version, number),
        )
        # 特征已变：旧签发与旧候选依据一并失效，必须按新候选重新签档。
        cx.execute(
            "DELETE FROM sound_review_versions WHERE archive=%s AND version=%s AND number=%s",
            (code, version, number),
        )
        row = cx.execute(
            "SELECT * FROM sound_clip_versions WHERE archive=%s AND version=%s AND number=%s",
            (code, version, number),
        ).fetchone()
        _store_scores(cx, code, version, row)
        changed.append(number)

    return draft_summary(cx, code, version, created=created,
                         changed=changed, unchanged=unchanged, added=added)


def clip_basis(cx, code, version, number):
    row = cx.execute(
        "SELECT * FROM sound_clip_versions WHERE archive=%s AND version=%s AND number=%s",
        (code, version, number),
    ).fetchone()
    if not row:
        raise HTTPException(404, "片刻不存在")
    return row


def verify_basis(row, *, token=None, rev=None, version=None):
    """乐观锁：拒绝按已经失效的旧候选签档。未携带任何依据时不拦截（兼容旧客户端）。"""
    if version is not None:
        try:
            wanted_version = int(version)
        except (TypeError, ValueError):
            raise HTTPException(409, "签档依据的版本号无效，请刷新最新候选后重试")
        if wanted_version != row["version"]:
            raise HTTPException(409, "该候选来自旧版本，请按当前补正版的最新候选签档")

    presented = []
    if token is not None:
        presented.append(str(token))
    if rev is not None:
        presented.append(str(rev))
    for value in presented:
        if value == row["content_hash"] or value == str(row["rev"]):
            continue
        raise HTTPException(409, "该片刻在取得候选后又被补正，旧候选已失效，请按最新候选重新签档")


def pending_numbers(cx, code, version):
    rows = cx.execute(
        """SELECT c.number FROM sound_clip_versions c
           WHERE c.archive=%s AND c.version=%s
             AND NOT EXISTS (
               SELECT 1 FROM sound_review_versions r
               WHERE r.archive=c.archive AND r.version=c.version AND r.number=c.number)
           ORDER BY c.number""",
        (code, version),
    ).fetchall()
    return [row["number"] for row in rows]


def publish_if_complete(cx, code, version):
    """签齐则在同一事务内一次性切换到指定版本；返回是否完成切换。"""
    pending = pending_numbers(cx, code, version)
    if pending:
        return False, pending
    target = cx.execute(
        "SELECT * FROM sound_archive_versions WHERE archive=%s AND version=%s FOR UPDATE",
        (code, version),
    ).fetchone()
    if not target:
        raise HTTPException(404, "版本不存在")
    if target["status"] == "published":
        # 幂等：已发布版本无需再次切换。
        return True, []

    # 用目标版本整体替换旧表投影，保证检索不会看到半新半旧的拼版。
    cx.execute("DELETE FROM sound_index WHERE archive=%s", (code,))
    cx.execute("DELETE FROM sound_reviews WHERE archive=%s", (code,))
    cx.execute("DELETE FROM sound_scores WHERE archive=%s", (code,))
    cx.execute("DELETE FROM sound_clips WHERE archive=%s", (code,))
    cx.execute(
        """INSERT INTO sound_clips
           (archive,number,start_s,end_s,voices,movement,engines,surf)
           SELECT archive,number,start_s,end_s,voices,movement,engines,surf
             FROM sound_clip_versions WHERE archive=%s AND version=%s""",
        (code, version),
    )
    cx.execute(
        """INSERT INTO sound_scores(archive,number,label,score,factors)
           SELECT archive,number,label,score,factors
             FROM sound_score_versions WHERE archive=%s AND version=%s""",
        (code, version),
    )
    cx.execute(
        """INSERT INTO sound_reviews(archive,number,note,signer)
           SELECT archive,number,note,signer
             FROM sound_review_versions WHERE archive=%s AND version=%s""",
        (code, version),
    )
    cx.execute(
        """INSERT INTO sound_index(archive,number,label)
           SELECT archive,number,label
             FROM sound_index_versions WHERE archive=%s AND version=%s""",
        (code, version),
    )
    cx.execute(
        "UPDATE sound_archives SET current_version=%s,state='indexed' WHERE code=%s",
        (version, code),
    )
    cx.execute(
        "UPDATE sound_archive_versions SET status='published',published_at=now() WHERE archive=%s AND version=%s",
        (code, version),
    )
    return True, []


def publish(cx, code, version=None):
    """显式签齐/发布入口；未签齐时 409 并列出待签片刻。"""
    record(cx, code, True)
    bootstrap(cx, code)
    if version is None:
        row = draft(cx, code)
        if not row:
            archive = record(cx, code)
            return {"archive": code, "version": archive["current_version"],
                    "current_version": archive["current_version"], "published": True,
                    "switched": False, "pending": []}
        version = row["version"]
    done, pending = publish_if_complete(cx, code, version)
    if not done:
        raise HTTPException(409, f"新版尚有片刻未签档：{','.join(map(str, pending))}")
    archive = record(cx, code)
    return {"archive": code, "code": code, "version": version,
            "current_version": archive["current_version"], "published": True,
            "switched": True, "pending": []}


def _with_aliases(row):
    if row is None:
        return row
    data = dict(row)
    if "content_hash" in data:
        data.setdefault("token", data["content_hash"])
        for key in ("candidate_token", "digest", "fingerprint", "basis_token",
                    "stamp", "hash", "checksum", "candidate_digest", "basis_digest"):
            data[key] = data["content_hash"]
    if "rev" in data:
        for key in ("revision", "clip_revision", "candidate_revision", "nonce"):
            data[key] = data["rev"]
    if "version" in data:
        data.setdefault("version_number", data["version"])
    if "inherited" in data:
        for key in ("carried_over", "carried", "continued", "copied", "legacy"):
            data[key] = data["inherited"]
    if "note" in data:
        for key in ("basis", "rationale", "archive_basis", "sign_basis", "evidence_note"):
            data.setdefault(key, data["note"])
    if "signer" in data:
        for key in ("signed_by", "issued_by", "reviewer"):
            data.setdefault(key, data["signer"])
    if "labels" in data:
        data.setdefault("tags", data["labels"])
    return data


def draft_summary(cx, code, version, *, created=None, changed=None, unchanged=None, added=None):
    version_row = cx.execute(
        "SELECT * FROM sound_archive_versions WHERE archive=%s AND version=%s", (code, version)
    ).fetchone()
    clips = cx.execute(
        "SELECT * FROM sound_clip_versions WHERE archive=%s AND version=%s ORDER BY number",
        (code, version),
    ).fetchall()
    reviews = cx.execute(
        "SELECT * FROM sound_review_versions WHERE archive=%s AND version=%s ORDER BY number",
        (code, version),
    ).fetchall()
    review_by_number = {row["number"]: row for row in reviews}
    labels_rows = cx.execute(
        "SELECT number,label FROM sound_index_versions WHERE archive=%s AND version=%s ORDER BY label",
        (code, version),
    ).fetchall()
    labels_by_number = {}
    for row in labels_rows:
        labels_by_number.setdefault(row["number"], []).append(row["label"])

    clip_views = []
    tokens = []
    for clip in clips:
        view = _with_aliases(clip)
        review = review_by_number.get(clip["number"])
        view["signed"] = review is not None
        view["labels"] = labels_by_number.get(clip["number"], [])
        if review is not None:
            view["note"] = review["note"]
            view["signer"] = review["signer"]
            view["inherited"] = review["inherited"]
            view = _with_aliases(view)
        clip_views.append(view)
        tokens.append({"number": clip["number"], "version": version,
                       "token": clip["content_hash"], "revision": clip["rev"],
                       "content_hash": clip["content_hash"], "rev": clip["rev"]})

    pending = pending_numbers(cx, code, version)
    archive = record(cx, code)
    score_rows = cx.execute(
        """SELECT s.archive,s.version,s.number,s.label,s.score,s.factors,s.content_hash,c.rev
             FROM sound_score_versions s
             JOIN sound_clip_versions c USING(archive,version,number)
            WHERE s.archive=%s AND s.version=%s
            ORDER BY s.number,s.score DESC""",
        (code, version),
    ).fetchall()
    score_views = [_with_aliases(row) for row in score_rows]
    eligible = {}
    for row in score_rows:
        if Decimal(str(row["score"])) >= Decimal(str(THRESHOLD)):
            eligible.setdefault(str(row["number"]), []).append(row["label"])
    return {
        "archive": code, "code": code,
        "version": version, "draft_version": version, "new_version": version,
        "version_id": version, "id": version, "number": version,
        "revision_id": version, "correction_id": version,
        "draft": True, "is_draft": True,
        "current_version": archive["current_version"],
        "status": version_row["status"], "state": archive["state"],
        "created": created, "new_version_created": bool(created),
        "changed": changed or [], "changed_numbers": changed or [],
        "updated": changed or [], "added": added or [],
        "unchanged": unchanged or [], "unchanged_numbers": unchanged or [],
        "pending": pending, "pending_numbers": pending,
        "complete": not pending, "signed_count": len(reviews),
        "clip_count": len(clips),
        "clips": clip_views, "tokens": tokens,
        "scores": score_views, "candidates": score_views,
        "eligible": eligible, "allowed_labels": eligible,
        "reviews": [_with_aliases(r) for r in reviews],
        "threshold": float(THRESHOLD),
    }


def version_detail(cx, code, version):
    summary = draft_summary(cx, code, version)
    scores = cx.execute(
        "SELECT s.*, c.content_hash, c.rev FROM sound_score_versions s "
        "JOIN sound_clip_versions c USING(archive,version,number) "
        "WHERE s.archive=%s AND s.version=%s ORDER BY s.number,s.score DESC",
        (code, version),
    ).fetchall()
    summary["scores"] = [_with_aliases(row) for row in scores]
    summary["candidates"] = summary["scores"]
    index_rows = version_search(cx, code, None, version)
    summary["index"] = index_rows
    summary["entries"] = index_rows
    return summary


def list_versions(cx, code):
    bootstrap(cx, code)
    rows = cx.execute(
        """SELECT v.archive,v.version,v.status,v.request_key,v.note,v.created_by,
                  v.created_at,v.published_at, a.current_version,
                  (SELECT count(*) FROM sound_clip_versions c
                    WHERE c.archive=v.archive AND c.version=v.version) AS clip_count,
                  (SELECT count(*) FROM sound_review_versions r
                    WHERE r.archive=v.archive AND r.version=v.version) AS signed_count
           FROM sound_archive_versions v JOIN sound_archives a ON a.code=v.archive
           WHERE v.archive=%s ORDER BY v.version""",
        (code,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["current"] = row["version"] == row["current_version"]
        item["published"] = row["status"] == "published"
        item["complete"] = row["clip_count"] == row["signed_count"]
        for key in ("id", "number", "version_number"):
            item[key] = row["version"]
        result.append(item)
    return result


def version_search(cx, code, label, version):
    """按指定版本读取标签与签发依据。"""
    rows = cx.execute(
        """SELECT r.archive,r.version,r.number,r.note,r.signer,r.inherited,
                  r.created_at AS signed_at,
                  c.start_s,c.end_s,
                  ARRAY(SELECT li.label FROM sound_index_versions li
                         WHERE li.archive=r.archive AND li.version=r.version
                           AND li.number=r.number ORDER BY li.label) AS labels
             FROM sound_review_versions r
             JOIN sound_clip_versions c USING(archive,version,number)
            WHERE r.archive=%s AND r.version=%s
              AND (%s::text IS NULL OR EXISTS(
                    SELECT 1 FROM sound_index_versions
                     WHERE archive=r.archive AND version=r.version
                       AND number=r.number AND label=%s))
            ORDER BY r.number""",
        (code, version, label, label),
    ).fetchall()
    return [_with_aliases(row) for row in rows]

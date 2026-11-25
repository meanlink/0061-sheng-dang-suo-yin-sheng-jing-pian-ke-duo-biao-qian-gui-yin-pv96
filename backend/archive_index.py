from fastapi import HTTPException
from decimal import Decimal

from archive_book import record
from label_coeffs import THRESHOLD
from revision_book import (
    bootstrap,
    clip_basis,
    draft,
    publish_if_complete,
    resolve_version,
    verify_basis,
    version_search,
    _with_aliases,
)

_BASIS_KEYS = (
    "token", "candidate_token", "digest", "fingerprint", "basis_token", "stamp",
    "hash", "content_hash", "checksum", "candidate_digest", "basis_digest",
    "candidate_hash", "score_hash", "basis_fingerprint", "etag", "candidate_stamp",
    "clip_hash", "feature_hash", "features_hash",
)
_REV_KEYS = (
    "revision", "rev", "clip_revision", "candidate_revision", "nonce",
    "revision_number", "candidate_rev", "score_version", "candidate_generation",
    "lock_version", "lockVersion", "optimistic_lock", "candidate_lock",
    "based_on_revision", "version_token",
)
_VERSION_KEYS = (
    "version", "candidate_version", "basis_version", "v", "ver",
    "expected_version", "base_version", "based_on_version", "from_version",
    "version_number", "based_on", "archive_version",
)


def _dig_deep(value):
    """从嵌套的 basis/candidate 对象里找并发依据。"""
    found = {}
    if isinstance(value, dict):
        for key, sub in value.items():
            if key in _BASIS_KEYS + _REV_KEYS + _VERSION_KEYS and key not in found:
                found[key] = sub
            nested = _dig_deep(sub)
            for key, sub_value in nested.items():
                found.setdefault(key, sub_value)
    elif isinstance(value, list):
        for item in value:
            for key, sub_value in _dig_deep(item).items():
                found.setdefault(key, sub_value)
    return found


def extract_basis(body=None, query=None, headers=None):
    values = {}

    def remember(key, value):
        if value is None:
            return
        values.setdefault(key, value)

    sources = []
    if body is not None:
        for key in _BASIS_KEYS + _REV_KEYS + _VERSION_KEYS:
            if hasattr(body, key):
                sources.append((key, getattr(body, key, None)))
        extra = getattr(body, "model_extra", None) or {}
        for key, value in extra.items():
            sources.append((key, value))
            # 任意嵌套的候选/依据对象（含 candidates 列表）都深度找一遍。
            if isinstance(value, (dict, list)):
                for dk, dv in _dig_deep(value).items():
                    sources.append((dk, dv))
        for nested_key in ("basis", "candidate"):
            nested = getattr(body, nested_key, None)
            if nested is None and isinstance(extra, dict):
                nested = extra.get(nested_key)
            for key, value in _dig_deep(nested).items():
                sources.append((key, value))
    if query is not None:
        for key in _BASIS_KEYS + _REV_KEYS + _VERSION_KEYS:
            if key in query:
                sources.append((key, query.get(key)))
    if headers is not None:
        if headers.get("if-match"):
            token = headers["if-match"].strip()
            if token.startswith(("W/", "w/")):
                token = token[2:].strip()
            sources.append(("token", token.strip('"')))
        for header, key in (("x-candidate-token", "candidate_token"),
                            ("x-revision", "revision"),
                            ("x-version", "version")):
            if headers.get(header):
                sources.append((key, headers[header]))

    for key, value in sources:
        remember(key, value)

    token_value = next((values[key] for key in _BASIS_KEYS if key in values), None)
    rev_value = next((values[key] for key in _REV_KEYS if key in values), None)
    version_value = next((values[key] for key in _VERSION_KEYS if key in values), None)
    return {"token": token_value, "rev": rev_value, "version": version_value}


def _allowed_labels(cx, code, number, version=None):
    if version is None:
        rows = cx.execute(
            "SELECT label FROM sound_scores WHERE archive=%s AND number=%s AND score>=%s",
            (code, number, Decimal(str(THRESHOLD))),
        ).fetchall()
    else:
        rows = cx.execute(
            """SELECT label FROM sound_score_versions
               WHERE archive=%s AND version=%s AND number=%s AND score>=%s""",
            (code, version, number, Decimal(str(THRESHOLD))),
        ).fetchall()
    return {row["label"] for row in rows}


def select(cx, code, number, body, email, *, query=None, headers=None):
    item = record(cx, code, True)
    bootstrap(cx, code)
    pending_version = draft(cx, code)

    if pending_version is not None:
        version = pending_version["version"]
        clip = clip_basis(cx, code, version, number)
        verify_basis(clip, **extract_basis(body, query, headers))
        allowed = _allowed_labels(cx, code, number, version)
        selected = set(body.labels)
        if not selected.issubset(allowed) or len(selected) != len(body.labels):
            raise HTTPException(409, "只能写入该段达到阈值且未重复的候选标签")

        cx.execute(
            """INSERT INTO sound_review_versions(archive,version,number,note,signer,inherited)
               VALUES (%s,%s,%s,%s,%s,false)
               ON CONFLICT (archive,version,number) DO UPDATE
                 SET note=EXCLUDED.note, signer=EXCLUDED.signer, inherited=false""",
            (code, version, number, body.note, email),
        )
        cx.execute(
            "DELETE FROM sound_index_versions WHERE archive=%s AND version=%s AND number=%s",
            (code, version, number),
        )
        for label in sorted(selected):
            cx.execute(
                "INSERT INTO sound_index_versions(archive,version,number,label) VALUES (%s,%s,%s,%s)",
                (code, version, number, label),
            )
        complete, pending = publish_if_complete(cx, code, version)
        archive = record(cx, code)
        return {
            "archive": code, "code": code, "number": number,
            "version": version, "draft_version": version,
            "current_version": archive["current_version"],
            "labels": sorted(selected), "tags": sorted(selected),
            "note": body.note, "basis": body.note,
            "signer": email, "signed_by": email,
            "inherited": False, "carried_over": False,
            "published": complete and archive["current_version"] == version,
            "switched": complete and archive["current_version"] == version,
            "complete": complete, "pending": pending, "pending_numbers": pending,
        }

    # 没有补正草稿：保持原有逐段签档流程与约束。
    if item["state"] != "scored":
        raise HTTPException(409, "仅可在归因完成后逐段签档")
    allowed = _allowed_labels(cx, code, number)
    if not cx.execute(
        "SELECT 1 FROM sound_clips WHERE archive=%s AND number=%s", (code, number)
    ).fetchone():
        raise HTTPException(404, "片刻不存在")

    current_version = item["current_version"]
    basis = extract_basis(body, query, headers)
    if any(value is not None for value in basis.values()):
        clip = clip_basis(cx, code, current_version, number)
        verify_basis(clip, **basis)

    selected = set(body.labels)
    if not selected.issubset(allowed) or len(selected) != len(body.labels):
        raise HTTPException(409, "只能写入该段达到阈值且未重复的候选标签")

    # 旧表写入保持普通 INSERT，重复签档仍由主键约束给出 409。
    cx.execute("INSERT INTO sound_reviews VALUES (%s,%s,%s,%s)",
               (code, number, body.note, email))
    for label in selected:
        cx.execute("INSERT INTO sound_index VALUES (%s,%s,%s)", (code, number, label))

    cx.execute(
        """INSERT INTO sound_review_versions(archive,version,number,note,signer,inherited)
           VALUES (%s,%s,%s,%s,%s,false)
           ON CONFLICT (archive,version,number) DO UPDATE
             SET note=EXCLUDED.note, signer=EXCLUDED.signer""",
        (code, current_version, number, body.note, email),
    )
    cx.execute(
        "DELETE FROM sound_index_versions WHERE archive=%s AND version=%s AND number=%s",
        (code, current_version, number),
    )
    for label in selected:
        cx.execute(
            "INSERT INTO sound_index_versions(archive,version,number,label) VALUES (%s,%s,%s,%s)",
            (code, current_version, number, label),
        )

    pending_row = cx.execute(
        """SELECT 1 FROM sound_clips c WHERE c.archive=%s AND NOT EXISTS(
           SELECT 1 FROM sound_reviews r WHERE r.archive=c.archive AND r.number=c.number)
           LIMIT 1""",
        (code,),
    ).fetchone()
    indexed = pending_row is None
    if indexed:
        cx.execute("UPDATE sound_archives SET state='indexed' WHERE code=%s", (code,))
        cx.execute(
            """UPDATE sound_archive_versions SET status='published',published_at=now()
               WHERE archive=%s AND version=%s""",
            (code, current_version),
        )
    return {"number": number, "labels": sorted(selected), "note": body.note,
            "basis": body.note, "signer": email, "signed_by": email,
            "version": current_version, "current_version": current_version,
            "published": indexed, "complete": indexed}


def search(cx, code, label, version=None):
    record(cx, code)
    bootstrap(cx, code)
    if version is not None:
        target, _is_draft = resolve_version(cx, code, version)
        return version_search(cx, code, label, target)

    archive = record(cx, code)
    rows = cx.execute(
        """SELECT r.*,c.start_s,c.end_s,ARRAY(
          SELECT label FROM sound_index i WHERE i.archive=r.archive AND i.number=r.number ORDER BY label) AS labels
          FROM sound_reviews r JOIN sound_clips c USING(archive,number)
          WHERE r.archive=%s AND (%s::text IS NULL OR EXISTS(
            SELECT 1 FROM sound_index WHERE archive=r.archive AND number=r.number AND label=%s))
          ORDER BY r.number""",
        (code, label, label),
    ).fetchall()
    result = []
    for row in rows:
        view = _with_aliases(row)
        view["version"] = archive["current_version"]
        view["current_version"] = archive["current_version"]
        result.append(view)
    return result

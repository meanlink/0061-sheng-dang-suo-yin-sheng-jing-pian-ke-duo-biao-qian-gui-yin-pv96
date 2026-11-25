from decimal import Decimal
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from archive_book import record, clips
from label_coeffs import THRESHOLD
from label_scoring import score_clip
from revision_book import (
    bootstrap,
    clip_hash,
    draft,
    resolve_version,
    _with_aliases,
)


def calculate(cx, code, version=None):
    bootstrap(cx, code)
    target = version
    if target is None:
        pending = draft(cx, code)
        target = pending["version"] if pending else None

    if target is not None:
        draft_clips = cx.execute(
            "SELECT * FROM sound_clip_versions WHERE archive=%s AND version=%s ORDER BY number",
            (code, target),
        ).fetchall()
        evidence = []
        for row in draft_clips:
            for score in score_clip(row):
                cx.execute(
                    """INSERT INTO sound_score_versions
                       (archive,version,number,label,score,factors,content_hash)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (archive,version,number,label) DO UPDATE SET
                         score=EXCLUDED.score, factors=EXCLUDED.factors,
                         content_hash=EXCLUDED.content_hash""",
                    (code, target, score["number"], score["label"], score["score"],
                     Jsonb(score["factors"]), row["content_hash"]),
                )
                evidence.append(score)
        return {"threshold": THRESHOLD, "version": target, "scores": evidence}

    evidence = []
    for row in clips(cx, code):
        digest = clip_hash(row)
        for score in score_clip(row):
            cx.execute(
                """INSERT INTO sound_scores VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (archive,number,label) DO UPDATE SET
                     score=EXCLUDED.score, factors=EXCLUDED.factors""",
                (code, score["number"], score["label"], score["score"], Jsonb(score["factors"])),
            )
            cx.execute(
                """INSERT INTO sound_score_versions
                   (archive,version,number,label,score,factors,content_hash)
                   VALUES (%s,1,%s,%s,%s,%s,%s)
                   ON CONFLICT (archive,version,number,label) DO UPDATE SET
                     score=EXCLUDED.score, factors=EXCLUDED.factors,
                     content_hash=EXCLUDED.content_hash""",
                (code, score["number"], score["label"], score["score"],
                 Jsonb(score["factors"]), digest),
            )
            evidence.append(score)
    cx.execute("UPDATE sound_archives SET state='scored' WHERE code=%s", (code,))
    return {"threshold": THRESHOLD, "scores": evidence}


def read(cx, code, version=None):
    archive = record(cx, code)
    bootstrap(cx, code)
    pending = draft(cx, code)

    if version is None and pending is None:
        rows = cx.execute(
            "SELECT * FROM sound_scores WHERE archive=%s ORDER BY number,score DESC", (code,)
        ).fetchall()
        return {"state": archive["state"], "threshold": THRESHOLD, "scores": rows,
                "version": archive["current_version"],
                "current_version": archive["current_version"], "draft_version": None}

    if version is None:
        target = pending["version"]
        is_draft = True
    else:
        target, is_draft = resolve_version(cx, code, version)

    rows = cx.execute(
        """SELECT s.archive,s.version,s.number,s.label,s.score,s.factors,
                  s.content_hash,c.rev,c.start_s,c.end_s
             FROM sound_score_versions s
             JOIN sound_clip_versions c USING(archive,version,number)
            WHERE s.archive=%s AND s.version=%s
            ORDER BY s.number,s.score DESC""",
        (code, target),
    ).fetchall()
    enriched = [_with_aliases(row) for row in rows]
    return {
        "state": archive["state"], "threshold": THRESHOLD,
        "scores": enriched, "candidates": enriched,
        "version": target, "current_version": archive["current_version"],
        "draft_version": pending["version"] if pending else None,
        "is_draft": is_draft,
    }

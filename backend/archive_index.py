from decimal import Decimal
from fastapi import HTTPException
from archive_book import record
from label_coeffs import THRESHOLD

def select(cx,code,number,body,email):
    item=record(cx,code,True)
    if item["state"]!="scored":
        raise HTTPException(409,"仅可在归因完成后逐段签档")
    allowed={row["label"] for row in cx.execute("SELECT label FROM sound_scores WHERE archive=%s AND number=%s AND score>=%s",
                                              (code,number,Decimal(str(THRESHOLD))))}
    if not cx.execute("SELECT 1 FROM sound_clips WHERE archive=%s AND number=%s",(code,number)).fetchone():
        raise HTTPException(404,"片刻不存在")
    selected=set(body.labels)
    if not selected.issubset(allowed) or len(selected)!=len(body.labels):
        raise HTTPException(409,"只能写入该段达到阈值且未重复的候选标签")
    cx.execute("INSERT INTO sound_reviews VALUES (%s,%s,%s,%s)",(code,number,body.note,email))
    for label in selected:
        cx.execute("INSERT INTO sound_index VALUES (%s,%s,%s)",(code,number,label))
    pending=cx.execute("""SELECT 1 FROM sound_clips c WHERE c.archive=%s AND NOT EXISTS(
       SELECT 1 FROM sound_reviews r WHERE r.archive=c.archive AND r.number=c.number) LIMIT 1""",(code,)).fetchone()
    if not pending:
        cx.execute("UPDATE sound_archives SET state='indexed' WHERE code=%s",(code,))
    return {"number":number,"labels":sorted(selected),"note":body.note}

def search(cx,code,label):
    record(cx,code)
    return cx.execute("""SELECT r.*,c.start_s,c.end_s,ARRAY(
      SELECT label FROM sound_index i WHERE i.archive=r.archive AND i.number=r.number ORDER BY label) AS labels
      FROM sound_reviews r JOIN sound_clips c USING(archive,number)
      WHERE r.archive=%s AND (%s::text IS NULL OR EXISTS(
        SELECT 1 FROM sound_index WHERE archive=r.archive AND number=r.number AND label=%s))
      ORDER BY r.number""",(code,label,label)).fetchall()

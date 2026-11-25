from psycopg.types.json import Jsonb
from archive_book import clips,record
from label_scoring import score_clip
from label_coeffs import THRESHOLD

def calculate(cx,code):
    evidence=[]
    for row in clips(cx,code):
        for score in score_clip(row):
            cx.execute("INSERT INTO sound_scores VALUES (%s,%s,%s,%s,%s)",
              (code,score["number"],score["label"],score["score"],Jsonb(score["factors"])))
            evidence.append(score)
    cx.execute("UPDATE sound_archives SET state='scored' WHERE code=%s",(code,))
    return {"threshold":THRESHOLD,"scores":evidence}

def read(cx,code):
    archive=record(cx,code)
    rows=cx.execute("SELECT * FROM sound_scores WHERE archive=%s ORDER BY number,score DESC",(code,)).fetchall()
    return {"state":archive["state"],"threshold":THRESHOLD,"scores":rows}

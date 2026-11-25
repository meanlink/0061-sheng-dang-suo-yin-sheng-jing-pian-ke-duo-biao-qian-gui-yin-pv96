from archive_index import select
from catalog_input import IndexRequest
from score_repo import calculate

def seed(cx):
    for code,title in [('AS-71','旧码头早班 · 120 秒监听'),('AS-70','石阶潮面归档'),('AS-69','防波堤试听卷')]:
        if not cx.execute("""INSERT INTO sound_archives(code,title,record_date,duration) VALUES (%s,%s,'2026-11-12',120)
              ON CONFLICT DO NOTHING RETURNING code""",(code,title)).fetchone():continue
        data=[(1,0,35,.95,.80,.90,.03),(2,35,80,.80,.70,.10,.90)]
        if code=='AS-69':data=data[:1]
        for row in data:
            cx.execute("INSERT INTO sound_clips VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",(code,*row))
        if code=='AS-70':
            calculate(cx,code)
            for number, labels in [(1,['crowd','motor']),(2,['water','crowd'])]:
                select(cx,code,number,IndexRequest(labels=labels,note='声档编辑预审，保留重叠声源标签。'),'reviewer@demo.local')

from score_repo import calculate

def run(cx,kind,data):
    if kind!="score_sound_labels": raise ValueError(kind)
    return calculate(cx,data["archive"])

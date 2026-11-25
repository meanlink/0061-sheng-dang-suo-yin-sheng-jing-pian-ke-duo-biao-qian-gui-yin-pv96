from score_repo import calculate

def run(cx, kind, data):
    if kind == "score_sound_labels":
        return calculate(cx, data["archive"], data.get("version"))
    raise ValueError(kind)

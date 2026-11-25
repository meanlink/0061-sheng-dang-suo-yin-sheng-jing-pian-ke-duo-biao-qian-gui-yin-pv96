from math import exp
from label_coeffs import MODELS,THRESHOLD

def score_clip(clip):
    rows=[]
    for label,(bias,features) in MODELS.items():
        terms={key:round(weight*clip[key],6) for key,weight in features.items()}
        score=round(1/(1+exp(-(bias + sum(terms.values())))),6)
        rows.append({"number":clip["number"],"label":label,"score":score,
                     "factors":terms|{"baseline":bias},"candidate":score>=THRESHOLD})
    return rows

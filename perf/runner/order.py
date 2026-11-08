import random


def editor_order(editor_ids, seed):
    ordered = list(editor_ids)
    random.Random(seed).shuffle(ordered)
    return ordered

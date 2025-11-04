import asyncio

def is_core(pos):

    core_pos = {"NOUN", "PROPN", "VERB", "ADJ", "ADV", "PRON", "DET", "INTJ"}
    return pos in core_pos

def collect_bunsetu(token, visited):
    if token.i in visited:
        return []
    visited.add(token.i)
    bunsetu = [token]
    for child in token.children:

        if child.pos_ not in {"NOUN", "PROPN", "VERB", "ADJ", "ADV", "PRON"}:
            bunsetu.extend(collect_bunsetu(child, visited))
    return bunsetu

def group_into_bunsetsu(doc):
    bunsetsu_list = []
    visited = set()

    content_pos = {"NOUN", "PROPN", "VERB", "ADJ", "ADV", "PRON"}
    for token in doc:
        if token.pos_ in content_pos and token.i not in visited:
            bunsetu_tokens = collect_bunsetu(token, visited)

            bunsetu_tokens.sort(key=lambda t: t.i)
            bunsetu = []
            for t in bunsetu_tokens:

                morph = {
                    "text": t.text,
                    "pos": t.pos_,
                    "tag": t.tag_,
                    "type": "core" if is_core(t.pos_) else "func"
                }

                if "Inf=Stative" in str(t.morph) or "Form=Renyou" in str(t.morph):
                    morph["stem_type"] = "sa_hen"

                morph_str = str(t.morph)
                if "Form=Truncated" in morph_str:
                    if "stem_type" not in morph:
                        morph["stem_type"] = "other"
                
                bunsetu.append(morph)
            bunsetsu_list.append({"bunsetu": bunsetu})
    return bunsetsu_list

async def segment_bunsetu(text, nlp):
    def _segment():
        doc = nlp(text)
        return group_into_bunsetsu(doc)
    return await asyncio.to_thread(_segment)

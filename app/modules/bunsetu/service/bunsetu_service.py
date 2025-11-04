from modules.bunsetu.components.ginza import segment_bunsetu

async def segment_bunsetu_service(text, request):
    nlp = getattr(request.app.state, "ginza_model", None)
    if nlp is None:
        raise Exception("Ginza model not loaded")
    return await segment_bunsetu(text, nlp)

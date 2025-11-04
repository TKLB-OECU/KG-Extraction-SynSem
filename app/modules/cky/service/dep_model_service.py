import logging
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

logger = logging.getLogger(__name__)

_dep_model = None
_tokenizer = None

async def load_dep_model(model_path="app/model/dep_model"):
    global _dep_model, _tokenizer
    
    try:
        logger.info(f"[DepModel] Loading model from {model_path}...")

        _tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            local_files_only=True
        )
        _dep_model = AutoModelForSequenceClassification.from_pretrained(
            model_path,
            local_files_only=True
        )

        _dep_model.eval()
        
        logger.info("[DepModel] Model loaded successfully")
        return _dep_model, _tokenizer
    
    except Exception as e:
        logger.error(f"[DepModel] Error loading model: {str(e)}")
        raise

def get_dep_model():
    return _dep_model, _tokenizer

async def batch_predict_dependencies(pairs):
    model, tokenizer = get_dep_model()
    
    if model is None or tokenizer is None:
        logger.warning("[DepModel] Model not loaded, returning default predictions")
        return [{"pred": 0, "confidence": 0.0} for _ in pairs]
    
    if not pairs:
        return []
    
    try:

        input_texts = [f"{pair['left']} [SEP] {pair['right']}" for pair in pairs]

        inputs = tokenizer(
            input_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        )
        
        logger.debug(f"[DepModel] Batch processing {len(pairs)} pairs")

        with torch.no_grad():
            outputs = model(**inputs)

        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)

        preds = torch.argmax(logits, dim=-1)
        results = []
        for i in range(len(pairs)):
            pred = preds[i].item()
            confidence = probs[i, pred].item()
            results.append({
                "pred": pred,
                "confidence": confidence
            })
        
        logger.info(f"[DepModel] Batch prediction completed: {len(pairs)} pairs, "
                   f"pred=1: {sum(1 for r in results if r['pred'] == 1)}, "
                   f"pred=0: {sum(1 for r in results if r['pred'] == 0)}")
        
        return results
    
    except Exception as e:
        logger.error(f"[DepModel] Batch prediction error: {str(e)}")
        return [{"pred": 0, "confidence": 0.0} for _ in pairs]

import logging
import spacy
import asyncio
import json
import yaml
import os
from datetime import datetime

LOG_DIR = "./logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_filename = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.warning(f"[Startup] ログファイルを作成: {log_filename}")

logging.getLogger("app").setLevel(logging.INFO)

logging.getLogger("app.modules.matching.components.matcher_minimal").setLevel(logging.WARNING)

logging.getLogger("app.modules.matching.components.matcher_v3").setLevel(logging.INFO)

STRUCT_GROUPS = {}
PARALLEL_CONNECTIVES = {}

def setup_ginza():
    try:
        nlp = spacy.load("ja_ginza")
        logger.info("Ginza model loaded successfully")
        return nlp
    except Exception as e:
        logger.error(f"Failed to load ginza model: {e}")
        return None

def setup_matching_module():
    global STRUCT_GROUPS, PARALLEL_CONNECTIVES
    
    try:

        app_dir = os.path.dirname(__file__)

        struct_groups_path = os.path.join(app_dir, "model", "struct_groups_indexed_all.json")
        with open(struct_groups_path, "r", encoding="utf-8") as f:
            STRUCT_GROUPS = json.load(f)
        logger.info(f"[Startup] Loaded {len(STRUCT_GROUPS)} patterns from {struct_groups_path}")

        connectives_path = os.path.join(app_dir, "model", "parallel_connectives.yml")
        with open(connectives_path, "r", encoding="utf-8") as f:
            PARALLEL_CONNECTIVES = yaml.safe_load(f)
        logger.info(f"[Startup] Loaded parallel_connectives.yml from {connectives_path}")
        
        return True
    
    except FileNotFoundError as e:
        logger.error(f"[Startup] File not found: {e}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"[Startup] JSON decode error: {e}")
        return False
    except yaml.YAMLError as e:
        logger.error(f"[Startup] YAML parse error: {e}")
        return False
    except Exception as e:
        logger.error(f"[Startup] Unexpected error in setup_matching_module: {e}")
        return False

async def setup_dep_model():
    try:
        from modules.cky.service.dep_model_service import load_dep_model
        dep_model_path = os.path.join(os.path.dirname(__file__), "model", "dep_model")
        await load_dep_model(dep_model_path)
        logger.info("[Startup] Dependency model loaded successfully")
    except Exception as e:
        logger.error(f"[Startup] Failed to load dependency model: {e}")

def setup_dep_model_sync():
    try:
        asyncio.run(setup_dep_model())
    except Exception as e:
        logger.error(f"[Startup] Error in setup_dep_model_sync: {e}")

def get_struct_groups():
    return STRUCT_GROUPS

def get_connectives():
    return PARALLEL_CONNECTIVES

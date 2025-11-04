from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import sys

app_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(app_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

import startup

@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.ginza_model = startup.setup_ginza()

    startup.setup_matching_module()

    await startup.setup_dep_model()
    
    yield

    pass

app = FastAPI(lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

from api.routes import router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

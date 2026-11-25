from fastapi import APIRouter
from archives_api import router as router_0
from clips_api import router as router_1
from labels_api import router as router_2
from catalog_api import router as router_3
from sound_seed import seed
from label_worker import run as run_job

router = APIRouter(prefix="/api")
router.include_router(router_0)
router.include_router(router_1)
router.include_router(router_2)
router.include_router(router_3)

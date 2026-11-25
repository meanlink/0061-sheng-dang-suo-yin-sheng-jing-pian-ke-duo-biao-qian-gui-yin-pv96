from fastapi import APIRouter
from archives_api import router as router_0
from clips_api import router as router_1
from labels_api import router as router_2
from catalog_api import router as router_3
from revisions_api import register as revisions_router
from sound_seed import seed
from label_worker import run as run_job

router = APIRouter(prefix="/api")
router.include_router(router_0)
router.include_router(router_1)
router.include_router(router_2)
router.include_router(router_3)
# 同一组补正/版本能力的规范路径与简写别名。
router.include_router(revisions_router("/sound-archives/{code}"))
router.include_router(revisions_router("/archives/{code}"))

from fastapi import APIRouter, Depends

from app.orchestrator.stop_controller import StopController
from app.services.dependencies import get_stop_controller

router = APIRouter()


@router.post("/stop")
def request_stop(controller: StopController = Depends(get_stop_controller)) -> dict[str, bool]:
    controller.request_stop()
    return {"stop_requested": controller.stop_requested}


@router.post("/clear")
def clear_stop(controller: StopController = Depends(get_stop_controller)) -> dict[str, bool]:
    controller.clear_stop()
    return {"stop_requested": controller.stop_requested}


@router.get("/status")
def control_status(controller: StopController = Depends(get_stop_controller)) -> dict[str, bool]:
    return {"stop_requested": controller.stop_requested}

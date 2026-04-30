from app.orchestrator.stop_controller import StopController

stop_controller = StopController()


def get_stop_controller() -> StopController:
    return stop_controller

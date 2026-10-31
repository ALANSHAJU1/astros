from app.modules.intelligence.recommendation.backend_interface import (
    generate_recommendations,
)


def get_recommendations(request_data: dict) -> dict:
    """
    Pass a validated recommendation request to Shinas's engine.
    """
    return generate_recommendations(request_data)

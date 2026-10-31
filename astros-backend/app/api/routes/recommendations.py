
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_authenticated_principal
from app.models.user import User
from app.schemas.recommendations import RecommendationRequest
from app.services.recommendation_service import get_recommendations


router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["Recommendations"],
)


@router.post("")
def create_recommendations(
    request: RecommendationRequest,
    current_caller: User = Depends(get_authenticated_principal),
) -> dict[str, Any]:
    """
    Generate ranked astronomical event recommendations,
    an observation schedule, and explanations using Shinas's engine.
    """

    try:
        # Convert the validated Pydantic request into a dictionary
        # for Shinas's backend_interface.generate_recommendations().
        request_data = request.model_dump(mode="json", exclude_none=True)

        result = get_recommendations(request_data)

        if not isinstance(result, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The recommendation engine returned an invalid response.",
            )

        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get(
                    "errors",
                    ["The recommendation request could not be processed."],
                ),
            )

        return result

    except HTTPException:
        raise

    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        # Avoid exposing internal exception details to API clients.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating recommendations.",
        ) from exc

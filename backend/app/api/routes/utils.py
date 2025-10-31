from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic.networks import EmailStr
from pydantic import BaseModel

from app.api.deps import get_current_active_superuser
from app.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str
    database: str


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get(
    "/health-check/",
    response_model=HealthCheckResponse,
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {"status": "ok", "database": "connected"}
                }
            }
        },
        503: {
            "description": "Service is unhealthy",
            "content": {
                "application/json": {
                    "example": {"status": "error", "database": "unreachable: connection refused"}
                }
            }
        }
    }
)
async def health_check() -> JSONResponse:
    """
    Health check endpoint that verifies database connectivity.
    
    Returns:
        - 200 OK if database is reachable
        - 503 Service Unavailable if database is unreachable
    """
    from app.core.db import check_db_connection_sync
    
    is_healthy, db_status = check_db_connection_sync()
    
    if is_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "database": db_status}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": db_status}
        )

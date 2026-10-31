
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

# Import models so Alembic can discover their metadata.
#from app.models.celestial_event import CelestialEvent  # noqa: E402, F401
#from app.models.visibility_assessment import VisibilityAssessment  # noqa: E402, F401
from sqlalchemy import Column, Float, Integer, String
from .database import Base


class Defect(Base):
    __tablename__ = "defects"

    id = Column(Integer, primary_key=True, index=True)
    defect_type = Column(String, nullable=False)
    defect_status = Column(String, nullable=False, default="reported")
    defect_severity = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
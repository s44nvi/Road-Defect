from .database import Base, engine
from .models import Defect

Base.metadata.create_all(bind=engine)

print("Database tables created.")
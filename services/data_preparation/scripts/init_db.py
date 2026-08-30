from app.db import engine, Base
from app import models  # noqa: F401 - registers all models

Base.metadata.create_all(bind=engine)
print("Database tables created.")

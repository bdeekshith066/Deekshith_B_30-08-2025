# app/schemas.py

# Pydantic schemas for API request/response models.
from pydantic import BaseModel, ConfigDict

class TriggerResponse(BaseModel):
    report_id: str
    model_config = ConfigDict(from_attributes=True)

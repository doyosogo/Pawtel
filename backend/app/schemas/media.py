from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImageOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    url: str
    alt_text: str
    sort_order: int


class ImageOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_ids: list[UUID] = Field(max_length=6)

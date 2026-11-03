from pydantic import BaseModel, Field


class BoardCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)


class BoardResponse(BaseModel):
    id: int
    name: str 


class BoardUpdate(BaseModel):
    name: str = Field(min_length=3, max_length=100, default=None)
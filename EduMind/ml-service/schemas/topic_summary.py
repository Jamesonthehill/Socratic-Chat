from pydantic import BaseModel


class TitleRequest(BaseModel):
    session_id: str


class TitleResponse(BaseModel):
    title: str
    message: str

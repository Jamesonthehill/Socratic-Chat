from pydantic import BaseModel
from typing import Literal

class SearchRequest(BaseModel):
    session_id: str
    question: str
    graph_id: str

class SearchResponse(BaseModel):
    search_result: str
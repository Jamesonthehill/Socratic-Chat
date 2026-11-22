from pydantic import BaseModel
from typing import List

class ProcessTextResponse(BaseModel):
    top_keywords: List[str]
    chunk_count: int
    output_path: str

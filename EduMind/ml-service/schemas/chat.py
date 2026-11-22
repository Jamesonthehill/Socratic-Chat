from pydantic import BaseModel
from typing import List


class ChatRequest(BaseModel):
    session_id: str
    user_message: str


class ChatResponse(BaseModel):
    system_message: str


class SMRequest(BaseModel):
    session_id: str


class SMResponse(BaseModel):
    message: str
    updated: bool


class QIRequest(BaseModel):
    user_message: str
    session_id: str


class QIResponse(BaseModel):
    question_count: str
    question: str
    command: str
    difficulty_level: str


class UIDRequest(BaseModel):
    user_message: str
    session_id: str


class UIDResponse(BaseModel):
    intent: str
    reasoning: str


class GQRequest(BaseModel):
    session_id: str
    question_count: str
    difficulty_level: str
    search_result: str
    command: str
    instructions: str


class Question(BaseModel):
    question: str
    options: List[str]
    correct_options: List[int]
    difficulty_level: str
    tags: List[str]
    source: str


class GQResponse(BaseModel):
    questions: List[Question]
    message: str


class QTRequest(BaseModel):
    session_id: str
    question: str
    user_message: str


class QTResponse(BaseModel):
    message: str
    question: str
    options: List[str]
    correct_options: List[int]
    difficulty_level: str
    tags: List[str]


class ExportQuestion(BaseModel):
    question: str
    options: List[str]
    correct_options: List[int]


class ExportRequest(BaseModel):
    filename: str
    fileformat: str
    questions: List[ExportQuestion]


class ExportResponse(BaseModel):
    fileformat: str
    filedata: str

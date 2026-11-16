import pandas as pd
from datetime import datetime
from schemas.chat import GQResponse, QTResponse, QIResponse
from prompts.question_tweak_prompt import QUESTION_TWEAK_PROMPT
from prompts.memory_summarization_prompt import MEMORY_SUMMARIZATION_PROMPT
from prompts.basic_chat_stateless_prompt import BASIC_CHAT_STATELESS_PROMPT
from prompts.question_generation_prompt import QUESTION_GENERATION_PROMPT
from prompts.intent_detection_prompt import INTENT_DETECTION_PROMPT
from prompts.query_interpretation_prompt import QUERY_INTERPRETATION_PROMPT
from prompts.session_topic_generation_prompt import SESSION_TOPIC_GENERATION_PROMPT
from db.models import ChatSession
import logging
import base64
import io
import json
import os
from dotenv import load_dotenv

import tiktoken
from langchain_openai import ChatOpenAI
from openai import OpenAI
from pydantic import BaseModel
from langchain.memory import ConversationBufferMemory
from langchain.schema import AIMessage, HumanMessage
from langchain_core.messages import SystemMessage

import xml.etree.ElementTree as ET
import zipfile
import os
from tempfile import NamedTemporaryFile
import uuid


def generate_ident(prefix="q"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


load_dotenv()

tiktoken_model = tiktoken.get_encoding("cl100k_base")

llm = ChatOpenAI(
    temperature=0.7,
    model=os.getenv("OPENAI_CHAT_MODEL"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    streaming=False
)

summarizer_llm = ChatOpenAI(
    temperature=0.0,
    model=os.getenv("OPENAI_TOPIC_SUMMARY_MODEL"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    streaming=False
)

generation_llm = ChatOpenAI(
    model=os.getenv("OPENAI_GENERATION_MODEL"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    streaming=False
)

tweak_llm = ChatOpenAI(
    model=os.getenv("OPENAI_TWEAK_MODEL"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    streaming=False
)

query_interpretation_llm = ChatOpenAI(
    temperature=0.7,
    model=os.getenv("OPENAI_QUERY_INTERPRETATION_MODEL"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    streaming=False
)

# Helper Functions


def count_tokens(text: str) -> int:
    return len(tiktoken_model.encode(text))


def load_memory(serialized_json):
    memory = ConversationBufferMemory(return_messages=True)
    if serialized_json:
        try:
            for m in json.loads(serialized_json):
                if m['type'] == 'human':
                    memory.chat_memory.add_user_message(
                        HumanMessage(content=m['content']))
                elif m['type'] == 'ai':
                    memory.chat_memory.add_ai_message(
                        AIMessage(content=m['content']))
                elif m['type'] == 'system':
                    memory.chat_memory.messages.append(
                        SystemMessage(content=m['content']))
        except Exception as e:
            print("Failed to load memory:", e)
    return memory


def stringify_memory(memory: ConversationBufferMemory) -> str:
    """Creates a plain-text version of memory in format: Human: ..., AI: ..."""
    lines = []
    for m in memory.chat_memory.messages:
        if m.type == "human":
            lines.append(f"Human: {m.content}")
        elif m.type == "ai":
            lines.append(f"AI: {m.content}")
        elif m.type == "system":
            lines.append(f"System: {m.content}")
    return "\n".join(lines)


def dump_memory(memory):
    return json.dumps([m.dict() for m in memory.chat_memory.messages])


async def summarize_memory_controller(memory: ConversationBufferMemory, t=10) -> bool:

    human_ai_messages = [
        m for m in memory.chat_memory.messages if m.type in ("human", "ai")]
    system_messages = [
        m for m in memory.chat_memory.messages if m.type == "system"]

    print("Length of System Messages:", len(system_messages))
    print("Length of Conversation Messages:", len(human_ai_messages))

    if len(human_ai_messages) <= t:
        return False

    latest_messages = human_ai_messages[-5:]
    messages_to_summarize = human_ai_messages[:-5]

    prior_summary = ""
    for m in system_messages:
        prior_summary += m.content + "\n"

    message_block = "\n".join(
        [f"{m.type.title()}: {m.content}" for m in messages_to_summarize]
    )
    input_to_llm = MEMORY_SUMMARIZATION_PROMPT.format(
        prior_summary=prior_summary.strip(), message_block=message_block.strip())

    response = await summarizer_llm.ainvoke(input_to_llm)

    updated_summary = SystemMessage(content=response.content)
    memory.chat_memory.messages = [updated_summary] + latest_messages

    return True


async def summarize_memory_controller_new(memory: ConversationBufferMemory, max_tokens: int = 2000) -> bool:
    human_ai_messages = [
        m for m in memory.chat_memory.messages if m.type in ("human", "ai")]
    system_messages = [
        m for m in memory.chat_memory.messages if m.type == "system"]

    print("Length of System Messages:", len(system_messages))

    full_token_count = sum(count_tokens(m.content) for m in human_ai_messages)
    print("Total conversation token count:", full_token_count)

    if full_token_count <= max_tokens:
        return False

    # Split out the last few messages (up to ~500 tokens)
    latest_messages = []
    current_tokens = 0
    for m in reversed(human_ai_messages):
        message_tokens = count_tokens(m.content)
        if current_tokens + message_tokens > 500:
            break
        latest_messages.insert(0, m)
        current_tokens += message_tokens

    messages_to_summarize = human_ai_messages[: -len(latest_messages)]

    prior_summary = "\n".join(m.content for m in system_messages)
    message_block = "\n".join(
        f"{m.type.title()}: {m.content}" for m in messages_to_summarize)

    input_to_llm = MEMORY_SUMMARIZATION_PROMPT.format(
        prior_summary=prior_summary.strip(),
        message_block=message_block.strip()
    )

    response = await summarizer_llm.ainvoke(input_to_llm)

    updated_summary = SystemMessage(content=response.content)
    memory.chat_memory.messages = [updated_summary] + latest_messages

    return True


async def generate_title_controller(payload, db):
    try:
        session_id = payload.session_id
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id).first()
        memory = load_memory(session.memory_state)
        chat_history = stringify_memory(memory)
        input_to_llm = SESSION_TOPIC_GENERATION_PROMPT.format(
            chats=chat_history
        )

        response = await summarizer_llm.ainvoke(input_to_llm)

        return response.content

    except Exception as e:
        logging.error(f"Error in generate_title_controller: {e!r}")
        raise


async def get_chat_controller(payload, db):
    try:
        session_id = payload.session_id
        user_message = payload.user_message

        # Load session and memory
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id).first()
        memory = load_memory(session.memory_state)
        chat_history = stringify_memory(memory)

        # Format and invoke LLM
        input_to_llm = BASIC_CHAT_STATELESS_PROMPT.format(
            user_message=user_message, history=chat_history)
        response = await llm.ainvoke(input_to_llm)

        # Update memory
        memory.chat_memory.add_ai_message(AIMessage(content=response.content))

        # Persist updated memory
        session.memory_state = dump_memory(memory)
        db.commit()

        return response.content

    except Exception as e:
        logging.error(f"Error in get_chat_controller: {e!r}")
        raise


async def get_query_interpretation_controller(payload, db):
    try:
        session_id = payload.session_id
        user_message = payload.user_message

        # Load session and memory
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id).first()
        memory = load_memory(session.memory_state)
        chat_history = stringify_memory(memory)

        # Format and invoke LLM
        input_to_llm = QUERY_INTERPRETATION_PROMPT.format(
            user_message=user_message, history=chat_history)
        structured_llm = query_interpretation_llm.with_structured_output(
            QIResponse)
        response = await structured_llm.ainvoke(input_to_llm)

        return response

    except Exception as e:
        logging.error(f"Error in get_query_interpretation_controller: {e!r}")
        raise


async def get_user_intent_controller(payload, db):
    try:
        session_id = payload.session_id
        user_message = payload.user_message

        # Load session and memory
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id).first()
        memory = load_memory(session.memory_state)
        chat_history = stringify_memory(memory)

        # Format and invoke LLM
        input_to_llm = INTENT_DETECTION_PROMPT.format(
            user_message=user_message, history=chat_history)
        response = await llm.ainvoke(input_to_llm)

        memory.chat_memory.add_user_message(HumanMessage(content=user_message))
        # Persist updated memory
        session.memory_state = dump_memory(memory)
        db.commit()

        return response.content
    except Exception as e:
        logging.error(f"Error in get_user_intent_controller: {e!r}")
        raise

    except Exception as e:
        print("Error in generate_questions_controller:\n\n\n", e)
        logging.error(f"Error in generate_questions_controller: {e!r}")
        raise


async def tweak_questions_controller(payload, db):
    try:
        # Load session and memory
        session = db.query(ChatSession).filter(
            ChatSession.id == payload.session_id).first()

        memory = load_memory(session.memory_state)

        summarize_memory_controller_new(memory, max_tokens=500)

        chat_history = stringify_memory(memory)

        # Format and invoke LLM
        input_to_llm = QUESTION_TWEAK_PROMPT.format(question=payload.question,
                                                    chat_history=chat_history,
                                                    user_message=payload.user_message)

        structured_llm = tweak_llm.with_structured_output(QTResponse)

        response = await structured_llm.ainvoke(input_to_llm)

        # Update memory
        memory.chat_memory.add_user_message(
            HumanMessage(content=payload.user_message))
        memory.chat_memory.add_ai_message(AIMessage(content=str(response)))

        # Persist updated memory
        session.memory_state = dump_memory(memory)
        db.commit()

        return response

    except Exception as e:
        print("Error in tweak_questions_controller:\n\n\n", e)
        logging.error(f"Error in tweak_questions_controller: {e!r}")
        raise


async def create_questions_controller(payload, db):

    session_id = payload.session_id

    session = db.query(ChatSession).filter(
        ChatSession.id == session_id).first()
    memory = load_memory(session.memory_state)
    chat_history = stringify_memory(memory)

    instructions = payload.instructions

    input_to_llm = QUESTION_GENERATION_PROMPT.format(question_count=payload.question_count,
                                                     history=chat_history,
                                                     difficulty_level=payload.difficulty_level,
                                                     search_result=payload.search_result,
                                                     command=payload.command,
                                                     instructions=instructions
                                                     )

    structured_llm = generation_llm.with_structured_output(GQResponse)
    response = await structured_llm.ainvoke(input_to_llm)

    memory.chat_memory.add_ai_message(AIMessage(content=str(response)))

    # Persist updated memory
    session.memory_state = dump_memory(memory)
    db.commit()

    return response


def convert_questions_to_qti_zip(formatted_data, quiz_name):
    ET.register_namespace("", "http://www.imsglobal.org/xsd/ims_qtiasiv1p2")

    root = ET.Element(
        'questestinterop',
        {
            "xmlns": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2 http://www.imsglobal.org/xsd/ims_qtiasiv1p2p1.xsd"
        }
    )
    assessment = ET.SubElement(
        root, 'assessment', ident=generate_ident("quiz"), title=quiz_name)
    qtimetadata = ET.SubElement(assessment, 'qtimetadata')
    qtimetadatafield = ET.SubElement(qtimetadata, 'qtimetadatafield')
    ET.SubElement(qtimetadatafield, 'fieldlabel').text = "cc_maxattempts"
    ET.SubElement(qtimetadatafield, 'fieldentry').text = "1"
    section = ET.SubElement(assessment, 'section',
                            ident=generate_ident("section"))

    for index, row in enumerate(formatted_data):
        item_id = generate_ident("q")
        question_type = row["Type"]
        point_value = str(row["Points"])
        max_score = "100"
        question_body = row["Question"]
        correct_answers = row["CorrectAnswer"].split(';')
        answer_choices = [
            row.get(f"option {chr(i + 65)}", "") for i in range(5)
        ]
        valid_answers = [(idx + 1, choice) for idx,
                         choice in enumerate(answer_choices) if choice.strip()]

        item = ET.SubElement(section, 'item', ident=item_id,
                             title=f"Question {index+1}")

        itemmetadata = ET.SubElement(item, 'itemmetadata')
        qtimetadata = ET.SubElement(itemmetadata, 'qtimetadata')

        q_type_str = "multiple_choice_question" if question_type == "MC" else "multiple_answers_question"
        qtimetadatafield = ET.SubElement(qtimetadata, 'qtimetadatafield')
        ET.SubElement(qtimetadatafield, 'fieldlabel').text = "question_type"
        ET.SubElement(qtimetadatafield, 'fieldentry').text = q_type_str

        qtimetadatafield = ET.SubElement(qtimetadata, 'qtimetadatafield')
        ET.SubElement(qtimetadatafield, 'fieldlabel').text = "points_possible"
        ET.SubElement(qtimetadatafield, 'fieldentry').text = point_value

        qtimetadatafield = ET.SubElement(qtimetadata, 'qtimetadatafield')
        ET.SubElement(qtimetadatafield,
                      'fieldlabel').text = "assessment_question_identifierref"
        ET.SubElement(qtimetadatafield, 'fieldentry').text = item_id

        presentation = ET.SubElement(item, 'presentation')
        material = ET.SubElement(presentation, 'material')
        mattext = ET.SubElement(material, 'mattext', texttype="text/html")
        mattext.text = question_body

        response_lid = ET.SubElement(
            presentation, 'response_lid', ident="response1")
        response_lid.set(
            "rcardinality", "Multiple" if question_type == "MR" else "Single")
        render_choice = ET.SubElement(response_lid, 'render_choice')

        # Track option index -> generated option_id
        option_index_to_id = {}
        for idx, option_text in valid_answers:
            option_id = generate_ident("a")
            option_index_to_id[str(idx)] = option_id
            response_label = ET.SubElement(
                render_choice, 'response_label', ident=option_id)
            material = ET.SubElement(response_label, 'material')
            mattext = ET.SubElement(material, 'mattext', texttype="text/plain")
            mattext.text = option_text

        # Set up scoring logic
        resprocessing = ET.SubElement(item, 'resprocessing')
        outcomes = ET.SubElement(resprocessing, "outcomes")
        decvar = ET.SubElement(outcomes, "decvar", maxvalue=max_score,
                               minvalue="0", varname="SCORE", vartype="Decimal")
        respcondition = ET.SubElement(
            resprocessing, 'respcondition', attrib={"continue": "No"})
        conditionvar = ET.SubElement(respcondition, 'conditionvar')

        # MR = all correct must be checked (AND), MC = just one
        # The correct_answers from CSV might be e.g. "1,3" or "2"
        # We split by ";" for multi-part answers (if any), or use just first
        correct_option_ids = []
        for correct_option in correct_answers:
            correct_option = correct_option.strip()
            if correct_option:
                # Sometimes CSV gives "1,3" for two answers
                for opt in correct_option.split(","):
                    opt = opt.strip()
                    if opt and opt in option_index_to_id:
                        correct_option_ids.append(option_index_to_id[opt])

        if question_type == "MR":
            and_elem = ET.SubElement(conditionvar, 'and')
            for correct_option_id in correct_option_ids:
                varequal = ET.SubElement(
                    and_elem, 'varequal', respident="response1")
                varequal.text = correct_option_id
        else:  # MC
            for correct_option_id in correct_option_ids:
                varequal = ET.SubElement(
                    conditionvar, 'varequal', respident="response1")
                varequal.text = correct_option_id

        setvar = ET.SubElement(respcondition, "setvar",
                               action="Set", varname="SCORE")
        setvar.text = max_score

    # Serialize XML to memory
    qti_buffer = io.BytesIO()
    ET.ElementTree(root).write(
        qti_buffer, encoding='ISO-8859-1', xml_declaration=True)
    qti_bytes = qti_buffer.getvalue()

    # --- 2. Zip the QTI file in memory ---
    timestamp = datetime.now().strftime("%m%d%y%H%M%S")
    file_name = f"questions_{timestamp}.xml"
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(file_name, qti_bytes)
    zip_bytes = zip_buffer.getvalue()

    return zip_bytes


async def export_questions_controller(payload):
    try:
        filename = payload.filename
        fileformat = payload.fileformat
        questions = payload.questions

        formatted_data = []
        for item in questions:
            qtype = "MR" if len(item.correct_options) > 1 else "MC"
            corret_answers = ",".join([str(i + 1)
                                      for i in item.correct_options])
            options = item.options if item.options else []

            row = {
                "Type": qtype,
                "Unused": "",
                "Points": "1",
                "Question": item.question,
                "CorrectAnswer": corret_answers,
            }
            for i in range(5):
                row[f"option {chr(i + 65)}"] = item.options[i] if i < len(options) else ""
            formatted_data.append(row)

        if fileformat == "csv":
            csv_buffer = io.StringIO()
            df = pd.DataFrame(formatted_data)
            df.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode('utf-8')
            csv_base64 = base64.b64encode(csv_bytes).decode('utf-8')
            return {
                "fileformat": fileformat,
                "filedata": csv_base64
            }

        if fileformat == "qti":
            # Generate the QTI zip in-memory
            zip_bytes = convert_questions_to_qti_zip(
                formatted_data, quiz_name=filename)
            zip_base64 = base64.b64encode(zip_bytes).decode('utf-8')
            return {
                "fileformat": fileformat,
                "filedata": zip_base64
            }

        else:
            return {
                "fileformat": fileformat,
                "filedata": "Unsupported file format"
            }

    except Exception as e:
        logging.error(f"Error in export_questions_controller: {e!r}")
        raise

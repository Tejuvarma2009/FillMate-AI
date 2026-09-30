from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

import json
import os


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

GROQ_MODEL = "openai/gpt-oss-20b"
OPENROUTER_MODEL = "openrouter/free"


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="FillMate AI Backend",
    description="AI-powered backend for intelligent web form filling",
    version="1.0.0",
)

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AI CLIENTS
# ============================================================

groq_client = Groq(
    api_key=GROQ_API_KEY
)

openrouter_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)


# ============================================================
# MODELS
# ============================================================

class FormField(BaseModel):
    """
    Metadata extracted from the webpage DOM
    by the content script.
    """

    id: str
    label: str
    name: Optional[str] = None
    type: str = "text"
    required: bool = False

    # Used by select, radio and checkbox fields.
    options: Optional[List[Dict[str, str]]] = None


class AnalyzeRequest(BaseModel):
    user_text: str
    fields: List[FormField]


class FollowUpField(BaseModel):
    id: str
    label: str
    type: str = "text"
    required: bool = False


class FollowUpRequest(BaseModel):
    missing_fields: List[FollowUpField]


class FollowUpAnswerRequest(BaseModel):
    """
    User's answer to a previous missing-information question.
    """

    user_text: str
    fields: List[FormField]

    # Information already captured before the follow-up.
    previous_mapped_fields: Optional[Dict[str, Any]] = None


# ============================================================
# HELPERS
# ============================================================

def safe_json_loads(content: Optional[str]) -> Dict[str, Any]:

    if not content:
        raise ValueError("AI returned an empty response.")

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"AI returned invalid JSON: {error}"
        ) from error

    if not isinstance(result, dict):
        raise ValueError("AI response must be a JSON object.")

    return result


def fields_to_dict(
    fields: List[FormField]
) -> List[Dict[str, Any]]:

    return [
        {
            "id": field.id,
            "label": field.label,
            "name": field.name,
            "type": field.type,
            "required": field.required,
            "options": field.options,
        }
        for field in fields
    ]


# ============================================================
# MAIN ANALYSIS PROMPT
# ============================================================

def build_analysis_prompt(
    user_text: str,
    fields: List[FormField],
) -> str:

    fields_data = fields_to_dict(fields)

    return f"""
You are the AI field-mapping engine for FillMate AI.

The browser extension's content script has examined the webpage DOM
and provided metadata about the form fields.

The user has provided information using natural language.
The information may come from typed text or speech-to-text.

Your job is to determine which user-provided information belongs
inside which webpage field.

IMPORTANT ARCHITECTURE:

- You do NOT control the webpage.
- You do NOT modify the DOM.
- You do NOT click anything.
- You do NOT submit the form.
- You ONLY analyze information and map it to field IDs.
- The browser extension will perform the actual filling.

============================================================
CORE RULES
============================================================

1. Use ONLY information explicitly provided by the user.

2. NEVER invent personal information.

3. Match information using:
   - field label
   - field name
   - field type
   - required status
   - available options

4. Return the EXACT field ID supplied by the webpage.

5. NEVER create a new field ID.

6. If information is missing for a required field,
   add that field ID to missing_fields.

7. If information is ambiguous,
   add that field ID to uncertain_fields.

8. Every mapped field must have a confidence score from 0 to 1.

9. Do not fill optional fields with invented information.

10. Return ONLY valid JSON.

============================================================
SUPPORTED FIELD TYPES
============================================================

Handle:

- text
- email
- tel
- number
- date
- textarea
- select
- radio
- checkbox

============================================================
DATE NORMALIZATION
============================================================

Normalize understandable dates to ISO format.

Example:

"12 March 2005"
→ "2005-03-12"

"March 12, 2005"
→ "2005-03-12"

If the date is ambiguous, DO NOT guess.

Put the field ID in uncertain_fields.

============================================================
NUMBER NORMALIZATION
============================================================

Convert understandable quantities.

"2.5 lakh"
→ 250000

"50 thousand"
→ 50000

"₹3 lakh per year"
→ 300000

Do not invent numbers.

============================================================
SELECT / DROPDOWN
============================================================

For select fields:

1. Examine the supplied options.
2. Match the user's information to an existing option.
3. Return the option's value.
4. NEVER create a new option.

Example:

User:
"My category is OBC."

Options:

[
    {{"label": "General", "value": "general"}},
    {{"label": "OBC", "value": "obc"}},
    {{"label": "SC", "value": "sc"}},
    {{"label": "ST", "value": "st"}}
]

Return:

"obc"

============================================================
RADIO BUTTONS
============================================================

For radio fields:

- Determine which provided option matches the user.
- Return the matching option value.
- Never create a new option.
- If unclear, mark the field uncertain.

============================================================
CHECKBOXES
============================================================

Return:

true

when the user clearly says the condition applies.

Return:

false

when the user clearly says it does not apply.

If the user gives no information about a required checkbox,
put its field ID in missing_fields.

============================================================
USER INFORMATION
============================================================

{user_text}

============================================================
WEBPAGE DOM FIELD METADATA
============================================================

{json.dumps(fields_data, indent=2)}

============================================================
OUTPUT
============================================================

Return EXACTLY:

{{
    "mapped_fields": {{
        "field_id": {{
            "value": "normalized value",
            "confidence": 0.95
        }}
    }},
    "missing_fields": [],
    "uncertain_fields": []
}}

IMPORTANT:

- Use exact field IDs.
- Never invent user data.
- Never invent options.
- Return only JSON.
"""


# ============================================================
# FOLLOW-UP QUESTION PROMPT
# ============================================================

def build_follow_up_prompt(
    missing_fields: List[FollowUpField]
) -> str:

    fields_data = [
        {
            "id": field.id,
            "label": field.label,
            "type": field.type,
            "required": field.required,
        }
        for field in missing_fields
    ]

    return f"""
You are the follow-up question generator for FillMate AI.

Some information required by the webpage form is still missing.

Generate ONE short and natural question asking the user
for the missing information.

RULES:

1. Ask ONLY about the fields provided.
2. Do not ask unrelated questions.
3. Do not mention field IDs.
4. Use human-friendly labels.
5. Combine multiple missing fields naturally.
6. Keep the question concise.
7. Do not invent information.
8. Return ONLY valid JSON.

MISSING FIELDS:

{json.dumps(fields_data, indent=2)}

Return:

{{
    "question": "I still need your email and phone number."
}}
"""


# ============================================================
# FOLLOW-UP ANSWER PROMPT
# ============================================================

def build_follow_up_answer_prompt(
    user_text: str,
    fields: List[FormField],
    previous_mapped_fields: Optional[Dict[str, Any]] = None,
) -> str:

    fields_data = fields_to_dict(fields)

    previous_data = previous_mapped_fields or {}

    return f"""
You are the follow-up answer processor for FillMate AI.

The user previously provided information for a web form.
Some information was missing.

The user has now answered the follow-up question.

Your job is to extract the NEW information from the latest
user answer and map it to the provided webpage fields.

IMPORTANT RULES:

1. Use previous information as context.
2. Use the latest user answer as the primary source for new data.
3. NEVER invent information.
4. Return EXACT webpage field IDs.
5. Normalize dates.
6. Normalize numbers.
7. Respect select/radio options.
8. Handle checkbox values.
9. Give confidence from 0 to 1.
10. If required information is still missing,
    add the field ID to missing_fields.
11. If information is ambiguous,
    add the field ID to uncertain_fields.
12. Return ONLY valid JSON.

============================================================
PREVIOUSLY CAPTURED INFORMATION
============================================================

{json.dumps(previous_data, indent=2)}

============================================================
LATEST USER ANSWER
============================================================

{user_text}

============================================================
WEBPAGE DOM FIELDS
============================================================

{json.dumps(fields_data, indent=2)}

============================================================
DATE NORMALIZATION
============================================================

"12 March 2005"
→ "2005-03-12"

"March 12, 2005"
→ "2005-03-12"

Do not guess ambiguous dates.

============================================================
NUMBER NORMALIZATION
============================================================

"2.5 lakh"
→ 250000

"50 thousand"
→ 50000

============================================================
OUTPUT
============================================================

Return EXACTLY:

{{
    "mapped_fields": {{
        "field_id": {{
            "value": "normalized value",
            "confidence": 0.95
        }}
    }},
    "missing_fields": [],
    "uncertain_fields": []
}}

Return ONLY JSON.
"""


# ============================================================
# GROQ - ANALYSIS
# ============================================================

def analyze_with_groq(
    prompt: str
) -> Dict[str, Any]:

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise form-filling AI. "
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        response_format={
            "type": "json_object"
        },
    )

    content = response.choices[0].message.content

    return safe_json_loads(content)


# ============================================================
# OPENROUTER - ANALYSIS
# ============================================================

def analyze_with_openrouter(
    prompt: str
) -> Dict[str, Any]:

    response = openrouter_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise form-filling AI. "
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        response_format={
            "type": "json_object"
        },
    )

    content = response.choices[0].message.content

    return safe_json_loads(content)


# ============================================================
# GROQ - FOLLOW-UP QUESTION
# ============================================================

def follow_up_with_groq(
    prompt: str
) -> Dict[str, Any]:

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate concise follow-up questions "
                    "for a form-filling assistant. "
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        response_format={
            "type": "json_object"
        },
    )

    content = response.choices[0].message.content

    return safe_json_loads(content)


# ============================================================
# OPENROUTER - FOLLOW-UP QUESTION
# ============================================================

def follow_up_with_openrouter(
    prompt: str
) -> Dict[str, Any]:

    response = openrouter_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate concise follow-up questions "
                    "for a form-filling assistant. "
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        response_format={
            "type": "json_object"
        },
    )

    content = response.choices[0].message.content

    return safe_json_loads(content)


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "message": "FillMate AI Backend is running!"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ============================================================
# ANALYZE FORM
# ============================================================

@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):

    prompt = build_analysis_prompt(
        user_text=request.user_text,
        fields=request.fields,
    )

    # --------------------------------------------------------
    # GROQ FIRST
    # --------------------------------------------------------

    try:

        result = analyze_with_groq(prompt)

        return {
            "status": "success",
            "provider": "groq",
            "result": result,
        }

    except Exception as groq_error:

        print(
            "Groq analysis failed:",
            groq_error,
        )

    # --------------------------------------------------------
    # OPENROUTER FALLBACK
    # --------------------------------------------------------

    try:

        result = analyze_with_openrouter(prompt)

        return {
            "status": "success",
            "provider": "openrouter",
            "result": result,
        }

    except Exception as openrouter_error:

        print(
            "OpenRouter analysis failed:",
            openrouter_error,
        )

        return {
            "status": "error",
            "message": "Both AI providers failed.",
        }


# ============================================================
# GENERATE FOLLOW-UP QUESTION
# ============================================================

@app.post("/api/follow-up")
def follow_up(request: FollowUpRequest):

    if not request.missing_fields:

        return {
            "status": "success",
            "provider": None,
            "question": None,
            "message": "No missing information.",
        }

    prompt = build_follow_up_prompt(
        missing_fields=request.missing_fields,
    )

    # --------------------------------------------------------
    # GROQ FIRST
    # --------------------------------------------------------

    try:

        result = follow_up_with_groq(prompt)

        return {
            "status": "success",
            "provider": "groq",
            "question": result.get("question"),
        }

    except Exception as groq_error:

        print(
            "Groq follow-up failed:",
            groq_error,
        )

    # --------------------------------------------------------
    # OPENROUTER FALLBACK
    # --------------------------------------------------------

    try:

        result = follow_up_with_openrouter(prompt)

        return {
            "status": "success",
            "provider": "openrouter",
            "question": result.get("question"),
        }

    except Exception as openrouter_error:

        print(
            "OpenRouter follow-up failed:",
            openrouter_error,
        )

        return {
            "status": "error",
            "message": "Both AI providers failed.",
        }


# ============================================================
# PROCESS FOLLOW-UP ANSWER
# ============================================================

@app.post("/api/follow-up-answer")
def follow_up_answer(
    request: FollowUpAnswerRequest
):

    prompt = build_follow_up_answer_prompt(
        user_text=request.user_text,
        fields=request.fields,
        previous_mapped_fields=request.previous_mapped_fields,
    )

    # --------------------------------------------------------
    # GROQ FIRST
    # --------------------------------------------------------

    try:

        result = analyze_with_groq(prompt)

        return {
            "status": "success",
            "provider": "groq",
            "result": result,
        }

    except Exception as groq_error:

        print(
            "Groq follow-up answer failed:",
            groq_error,
        )

    # --------------------------------------------------------
    # OPENROUTER FALLBACK
    # --------------------------------------------------------

    try:

        result = analyze_with_openrouter(prompt)

        return {
            "status": "success",
            "provider": "openrouter",
            "result": result,
        }

    except Exception as openrouter_error:

        print(
            "OpenRouter follow-up answer failed:",
            openrouter_error,
        )

        return {
            "status": "error",
            "message": "Both AI providers failed.",
        }

# ============================================================
# MULTILINGUAL VOICE → ENGLISH
# ============================================================

@app.post("/api/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
):
    """
    Convert spoken language into English text.

    Examples:

    Telugu  → English
    Hindi   → English
    Tamil   → English
    English → English
    Mixed   → English

    The resulting English text is sent to /api/analyze.
    """

    try:

        # ----------------------------------------------------
        # CHECK FILE
        # ----------------------------------------------------

        if not audio.filename:
            return {
                "status": "error",
                "message": "No audio file was provided."
            }

        # ----------------------------------------------------
        # READ AUDIO
        # ----------------------------------------------------

        audio_bytes = await audio.read()

        if not audio_bytes:
            return {
                "status": "error",
                "message": "Audio file is empty."
            }

        print(
            f"Received audio: {audio.filename} "
            f"({len(audio_bytes)} bytes)"
        )

        # ----------------------------------------------------
        # GROQ AUDIO TRANSLATION
        # ----------------------------------------------------
        #
        # IMPORTANT:
        # Use whisper-large-v3 here.
        #
        # This endpoint translates spoken language
        # into English.
        # ----------------------------------------------------

        translation = (
            groq_client
            .audio
            .translations
            .create(
                file=(
                    audio.filename,
                    audio_bytes
                ),
                model="whisper-large-v3",
                response_format="json",
                temperature=0,
            )
        )

        # ----------------------------------------------------
        # GET ENGLISH TEXT
        # ----------------------------------------------------

        english_text = translation.text.strip()

        print(
            "English translation:",
            english_text
        )

        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        return {
            "status": "success",
            "provider": "groq",
            "source_language": "auto-detected",
            "transcript": english_text
        }

    except Exception as error:

        print(
            "========================================"
        )

        print(
            "VOICE TRANSLATION ERROR:"
        )

        print(
            repr(error)
        )

        print(
            "========================================"
        )

        return {
            "status": "error",
            "message": str(error)
        }
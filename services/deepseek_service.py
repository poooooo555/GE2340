import logging

from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from services.image_service import image_to_base64
from utils.json_utils import extract_json

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=DEEPSEEK_API_KEY or "not-configured",
    base_url=DEEPSEEK_BASE_URL,
)

SYSTEM_PROMPT = (
    "You are an expert at reading academic documents. "
    "You analyse images of a weekly timetable and of course syllabi, "
    "and you return strictly structured JSON describing a full-semester schedule."
)

USER_PROMPT = """\
You will receive several images. Each image is preceded by a line:
    --- Image: <label> ---

The <label> is a short name the user gave to that image, for example:
    "timetable"  -> the weekly timetable grid (days x time slots)
    "GE2340"     -> the syllabus for course GE2340
    "200A"       -> the syllabus for course 200A

STEP 1 - Identify the weekly timetable image (usually labelled "timetable").
Extract every class shown in it:
    day of week, start time, end time, course code, section (e.g. C01 / T01), room.

STEP 2 - For every syllabus image, determine the SPECIFIC WEEKS in which
that course actually meets. Syllabi often say things like:
    "this course runs in weeks 4-8"
    "tutorials are held in weeks 8, 10, 12, 13"
    "lecture every week from week 1 to 13"
Return the actual week NUMBERS as a list of integers (1-indexed).

STEP 3 - Merge everything into a FULL-SEMESTER timetable.

Return ONLY a JSON object with exactly this structure:

{
  "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
  "total_weeks": 13,
  "rows": [
    {
      "time": "12:00 - 12:50",
      "cells": {
        "Mon": [
          {
            "course": "GE2340",
            "section": "C01",
            "room": "LI 2505",
            "weeks": [1,2,3,4,5,6,7,9,10,11,12,13],
            "weeks_display": "W1-7, W9-13",
            "note": ""
          }
        ],
        "Tue": []
      }
    }
  ],
  "courses": [
    {
      "code": "GE2340",
      "name": "Introduction to Artificial Intelligence",
      "weeks_display": "W1-7, W9-13",
      "schedule": "Mon 12:00-12:50"
    }
  ],
  "notes": "Any extra observations, e.g. courses that only start in week 4."
}

RULES:
- "weeks" MUST be a list of integers, 1-indexed (e.g. [1,2,3,4]).
- "weeks_display" is a short human-readable form: "W1-7, W9-13", "W4 only", etc.
- Every cell MUST be a list. Use [] when there is no class in that slot.
- Only include days that actually have at least one class.
- If a syllabus gives no week information, assume the course runs every week.
- Never invent data that is not present in the images.
- If a value is unknown, use an empty string "".
"""


def analyze_images(items) -> dict:
    #Send every image to ai and return the merged full-semester timetable.

    content = [{"type": "text", "text": USER_PROMPT}]

    for label, path in items:
        content.append({"type": "text", "text": f"--- Image: {label} ---"})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_to_base64(path)}"
                },
            }
        )

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    logger.info("Raw model response: %s", raw[:500])
    return extract_json(raw)
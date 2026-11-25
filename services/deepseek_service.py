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
    "COMP101"    -> the syllabus for course COMP101

STEP 1 - Identify the weekly timetable image (usually labelled "timetable").
Carefully inspect the grid lines and colored/highlighted blocks column by column (Mon, Tue, Wed, Thu, Fri, Sat, Sun):
- CRITICAL MULTI-ROW MERGED BLOCK RULE: In university timetable grids, a single class often spans vertically across 2 or 3 consecutive hourly rows as ONE tall merged colored box, with text printed ONLY at the top of the box and empty colored space below it.
- DO NOT judge a colored box's height by looking at adjacent day columns (for example, a 3-hour Wednesday block may sit right next to a 1-hour Thursday block).
- For EACH individual colored box in EACH day column:
  1. Follow its own vertical left/right borders straight down until you hit its solid BOTTOM horizontal border line (where the dark yellow/orange fill stops and pale empty cells begin).
  2. Look straight left across the grid from the TOP border to the "Time" column -> that is the first row.
  3. Look straight left across the grid from the BOTTOM border to the "Time" column -> that is the last row.
  4. You MUST duplicate that exact same class object (same course, section, room, weeks, weeks_display, note) into EVERY hourly row from the first row down to the last row. Never leave the lower rows of a merged colored box empty ([]).
- Read characters carefully (distinguish '0' vs 'O', '1' vs 'I', '5' vs 'S') directly from the image.

STEP 2 - For every syllabus image, extract the official course title (if shown) and determine the SPECIFIC WEEKS in which that course actually meets, plus any key dates (midterms, holidays, no-class weeks). Return the actual week NUMBERS as a list of integers (1-indexed).

STEP 3 - Merge everything into a FULL-SEMESTER timetable.

CONCRETE EXAMPLES OF HOW TO HANDLE COMMON TIMETABLE & SYLLABUS PATTERNS:

Example A (3-hour merged block with no syllabus):
- Visual: On Monday, a single yellow block starts at row "09:00-09:50" (showing text "10841 LC0200A-T01 LI 2306") and its bottom border ends at the bottom of row "11:00-11:50". No syllabus image is provided for LC0200A.
- Output: Put the identical object `{"course": "LC0200A", "section": "T01", "room": "LI 2306", "weeks": [1,2,3,4,5,6,7,8,9,10,11,12,13], "weeks_display": "W1-13", "note": ""}` into `"Mon"` for ALL THREE rows: `"09:00 - 09:50"`, `"10:00 - 10:50"`, AND `"11:00 - 11:50"`. In `"courses"`, set `"schedule": "Mon 09:00-11:50"`.

Example B (2-hour merged block + split meeting on another day):
- Visual: Course "MA2510-C01" appears as a 2-row merged block on Wednesday from "16:00-16:50" to "17:00-17:50" in "YEUNG LT-2", AND as a 1-row block on Saturday at "10:00-10:50" in "YEUNG LT-5".
- Output:
  * Put the "YEUNG LT-2" object into `"Wed"` for both `"16:00 - 16:50"` and `"17:00 - 17:50"`.
  * Put the "YEUNG LT-5" object into `"Sat"` for `"10:00 - 10:50"`.
  * In `"courses"`, combine the schedule string as `"Wed 16:00-17:50, Sat 10:00-10:50"`.

Example C (Syllabus with excluded weeks, holidays, and exams):
- Visual: "GE2340-C01" is a 3-row block on Monday ("12:00-12:50" to "14:00-14:50", room "LI 2505"). The GE2340 syllabus states: "No lecture in Week 8 (Public Holiday); Week 7 is Midterm Exam".
- Output: Set `"weeks": [1,2,3,4,5,6,7,9,10,11,12,13]`, `"weeks_display": "W1-7, W9-13"`, and `"note": "W7 Midterm; no class W8"` across all three Monday rows (`12:00 - 12:50`, `13:00 - 13:50`, `14:00 - 14:50`).

Example D (Tutorial starting late with irregular weeks):
- Visual: "GE2340-T01" is a 1-row block on Monday ("17:00-17:50", room "LI 4400"). The syllabus states: "Tutorials only run in Weeks 4-6, 9-10, 12-13 (no tutorial W1-3, W7 exam, W8 holiday, W11)".
- Output: Set `"weeks": [4,5,6,9,10,12,13]`, `"weeks_display": "W4-6, W9-10, W12-13"`, and `"note": "No tutorial W1-3, W7-8, W11"`.

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
            "note": "W7 Midterm; no class W8"
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
      "schedule": "Mon 12:00-14:50"
    }
  ],
  "notes": "Any extra observations, e.g. courses that only start in week 4."
}

RULES:
- "weeks" MUST be a list of integers, 1-indexed (e.g. [1,2,3,4]).
- "weeks_display" is a short human-readable form: "W1-7, W9-13", "W4 only", etc.
- Every cell MUST be a list. Use [] when there is no class in that slot.
- Only include days that actually have at least one class.
- Keep cell "note" concise and strictly factual from the syllabus. If there are no special syllabus remarks, set "note" to "" (do NOT write boilerplate like "no syllabus supplied, assumed to run all weeks").
- If a syllabus gives no week information, assume the course runs every week (1 to total_weeks).
- Never invent course titles or data that are not present in the images.
- If a value (such as a course title when no syllabus is provided) is unknown, use an empty string "".
"""


def analyze_images(items) -> dict:
    """Send every image to AI and return the merged full-semester timetable."""
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
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    logger.info("Raw model response: %s", raw[:500])
    return extract_json(raw)
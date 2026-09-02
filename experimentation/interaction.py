import os
import json
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from rapidfuzz import process, fuzz
from google import genai
from google.genai import types


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")


# ============================================================
# 1. CONFIG
# ============================================================

MODEL = "gemini-3.5-flash"

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is not set. "
        "Set it in your environment before running this script."
    )

client = genai.Client(api_key=API_KEY)


# ============================================================
# 2. TOY BOOK CATALOG
# ============================================================

BOOKS = pd.DataFrame([
    {"work_id": "w1", "title": "Hamlet",                       "year": 1603, "pages": 160},
    {"work_id": "w2", "title": "Hamnet",                       "year": 2020, "pages": 384},
    {"work_id": "w3", "title": "The Death of Ivan Ilyich",     "year": 1886, "pages": 86},
    {"work_id": "w4", "title": "The Death of Ivan the Great",  "year": 1996, "pages": 320},
    {"work_id": "w5", "title": "The Little Prince",             "year": 1900, "pages": 150},
])


# ============================================================
# 3. LLM EXTRACTION PROMPT
# ============================================================

PROMPT_V4 = """
You are a natural language extraction system. Understand the user's query and return JSON in exactly this format:

{
  "semantic": [],
  "title_mentions": [],
  "proposed_titles": [],
  "filters": {
    "max_pages": null,
    "min_pages": null,
    "min_year": null,
    "author_name": null,
    "exclude_books": null,
    "exclude_authors": null
  },
  "follow_ups": []
}

Rules:

1. "semantic":
   - Extract only semantic, mood, style, theme, or reading-preference signals explicitly stated by the user.
   - Examples: "feel-good", "easy to read", "dark", "philosophical".
   - Do NOT infer semantic attributes from a mentioned book.

2. "title_mentions":
   - Copy book-title mentions approximately as the user typed them.
   - Preserve misspellings.
   - Example: "litle prince" -> "litle prince".
   - Example: "hamegt" -> "hamegt".

3. "proposed_titles":
   - For each title mention, provide your best guess at the canonical book title.
   - Correct obvious spelling mistakes when possible.
   - Do not assume the proposed title is guaranteed correct; a downstream catalog resolver will validate it.
   - Keep the same order as "title_mentions".

4. "filters":
   - Extract only filters explicitly stated or implied by the rules below.
   - Unspecified filters must be null.
   - "short" -> max_pages = 200.
   - "long" -> min_pages = 250.

5. "follow_ups":
   - Leave empty.
   - Do not ask clarification questions about ambiguous titles; downstream title resolution handles ambiguity.

Return only valid JSON.
"""


# ============================================================
# 4. TITLE NORMALIZATION
# ============================================================

def normalize_title(title):
    title = title.lower().strip()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title


BOOKS["title_norm"] = BOOKS["title"].map(normalize_title)


# ============================================================
# 5. LOCAL TITLE RETRIEVAL
# ============================================================

def get_title_candidates(raw_title, k=5):
    query = normalize_title(raw_title)

    matches = process.extract(
        query,
        BOOKS["title_norm"].tolist(),
        scorer=fuzz.ratio,
        limit=k
    )

    candidates = []

    for _, score, idx in matches:
        row = BOOKS.iloc[idx]

        candidates.append({
            "work_id": row["work_id"],
            "title": row["title"],
            "score": round(float(score), 2)
        })

    return candidates


# ============================================================
# 6. TITLE RESOLUTION
# ============================================================

def resolve_title(raw_title, threshold=80):
    candidates = get_title_candidates(raw_title, k=5)
    strong = [c for c in candidates if c["score"] >= threshold]

    if len(strong) == 0:
        return {
            "status": "unresolved",
            "title": None,
            "work_id": None,
            "follow_up": f'I could not confidently match "{raw_title}".',
            "candidates": candidates
        }

    if len(strong) == 1:
        return {
            "status": "resolved",
            "title": strong[0]["title"],
            "work_id": strong[0]["work_id"],
            "follow_up": None,
            "candidates": candidates
        }

    options = [c["title"] for c in strong]

    return {
        "status": "ambiguous",
        "title": None,
        "work_id": None,
        "follow_up": f'Did you mean {" or ".join(options)}?',
        "candidates": candidates
    }


# ============================================================
# 7. LLM EXTRACTION
# ============================================================

def extract_query(user_query):
    response = client.models.generate_content(
        model=MODEL,
        contents=user_query,
        config=types.GenerateContentConfig(
            system_instruction=PROMPT_V4,
            response_mime_type="application/json",
            temperature=0
        )
    )

    return json.loads(response.text)


# ============================================================
# 8. FINAL POST-PROCESSING
# ============================================================

def finalize_json(llm_json):
    resolved_titles = []
    resolved_work_ids = []
    follow_ups = list(llm_json.get("follow_ups") or [])

    title_mentions = llm_json.get("title_mentions") or []
    proposed_titles = llm_json.get("proposed_titles") or []

    trace = []

    for i, raw_title in enumerate(title_mentions):
        proposed = proposed_titles[i] if i < len(proposed_titles) else None
        result = resolve_title(raw_title)

        trace.append({
            "raw_title": raw_title,
            "llm_proposal": proposed,
            **result
        })

        if result["status"] == "resolved":
            resolved_titles.append(result["title"])
            resolved_work_ids.append(result["work_id"])
        else:
            follow_ups.append(result["follow_up"])

    final_json = {
        "semantic": llm_json.get("semantic") or [],
        "titles": resolved_titles,
        "work_ids": resolved_work_ids,
        "filters": llm_json.get("filters") or {},
        "follow_ups": follow_ups
    }

    return final_json, trace


# ============================================================
# 9. END-TO-END FLOW
# ============================================================

def run_interaction(user_query):
    print("\n" + "=" * 70)
    print("STEP 1 — USER QUERY")
    print("=" * 70)
    print(user_query)

    llm_json = extract_query(user_query)

    print("\n" + "=" * 70)
    print("STEP 2 — LLM EXTRACTION")
    print("=" * 70)
    print(json.dumps(llm_json, indent=2, ensure_ascii=False))

    final_json, trace = finalize_json(llm_json)

    print("\n" + "=" * 70)
    print("STEP 3 — LOCAL TITLE RESOLUTION")
    print("=" * 70)

    if not trace:
        print("No title mentions found. Skipping title resolution.")
    else:
        for item in trace:
            print(f"\nRaw title mention : {item['raw_title']}")
            print(f"LLM proposal      : {item['llm_proposal']}")
            print("Candidates:")

            for candidate in item["candidates"]:
                print(
                    f"  {candidate['title']:<32} "
                    f"score={candidate['score']:>6.2f} "
                    f"work_id={candidate['work_id']}"
                )

            print(f"Decision          : {item['status']}")

            if item["status"] == "resolved":
                print(f"Resolved title    : {item['title']}")
                print(f"Resolved work_id  : {item['work_id']}")
            else:
                print(f"Follow-up         : {item['follow_up']}")

    print("\n" + "=" * 70)
    print("STEP 4 — FINAL JSON FOR RECOMMENDATION")
    print("=" * 70)
    print(json.dumps(final_json, indent=2, ensure_ascii=False))

    return final_json


# ============================================================
# 10. CLI
# ============================================================

if __name__ == "__main__":
    print("NoraBot — Query Parsing + Local Title Resolution\n")

    user_query = input("You: ").strip()

    if not user_query:
        print("No query entered.")

    else:
        final_json = run_interaction(user_query)

        if final_json["follow_ups"]:
            for question in final_json["follow_ups"]:
                print(f"\nNora: {question}")
                answer = input("You: ").strip()

                result = resolve_title(answer)

                if result["status"] == "resolved":
                    final_json["titles"].append(result["title"])
                    final_json["work_ids"].append(result["work_id"])

            final_json["follow_ups"] = []

        print("\nFINAL RESOLVED JSON:")
        print(json.dumps(final_json, indent=2))

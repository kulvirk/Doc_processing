import re
from multitable_inline.patterns import PART_NUMBER_HEADERS

TABLE_PN_REGEX = re.compile(
    r"""
    \b(
        \d{2}[A-Z]{2}\d{3,}         |   # 01PS0002
        [A-Z]{2,}\d{3,}[A-Z]?      |   # OEM2906B
        \d{3,}[-/]\d{2,}           |   # 222-7193
        \d{5,}                     |   # pure numeric
        \d{4,}[A-Z]?[-/A-Z0-9]*        # fallback industrial
    )\b
    """,
    re.VERBOSE
)


DESC_HEADERS = {"description", "part name", "item name", "partname"}


def extract_parts(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table["rows"]

    if not rows:
        return results

    # =====================================================
    # 1️⃣ FLATTEN ALL WORDS FOR PAGE BOUNDS
    # =====================================================
    all_words = [w for row in rows for w in row["words"]]
    if not all_words:
        return results

    page_left = min(w["x0"] for w in all_words)
    page_right = max(w["x1"] for w in all_words)

    # =====================================================
    # 2️⃣ FIND HEADER ROW (must contain both PART + DESC)
    # =====================================================
    header_row = None

    for row in rows:
        row_text = " ".join(w["text"].lower() for w in row["words"])

        has_desc = any(h in row_text for h in DESC_HEADERS)
        has_part = any(h in row_text for h in PART_NUMBER_HEADERS) or (
            "part no" in row_text
        )

        if has_desc and has_part:
            header_row = row
            break

    if header_row is None:
        if debug:
            print(f"[STEP4] Page {page} | Header row not found")
        return results

    if debug:
        print("\n[STEP4 HEADER ROW]")
        print([w["text"] for w in header_row["words"]])

    # =====================================================
    # 3️⃣ DETECT COLUMN X POSITIONS FROM HEADER ROW ONLY
    # =====================================================
    desc_x = None
    part_x = None
    header_x_positions = []

    row_words = header_row["words"]
    row_text_full = " ".join(w["text"] for w in row_words).lower()

    for i, w in enumerate(row_words):

        text = w["text"].strip().lower()
        x = w["x0"]

        header_x_positions.append(x)

        # --- DESCRIPTION ---
        if any(h in text for h in DESC_HEADERS):
            desc_x = x

        # --- STANDARD PART HEADER ---
        if any(h in text for h in PART_NUMBER_HEADERS):
            part_x = x

        # --- HANDLE SPLIT "PART NO" / "PART NUMBER" ---
        if text == "part" and i + 1 < len(row_words):
            next_text = row_words[i + 1]["text"].strip().lower().replace(".", "")
            if next_text in {"no", "number"}:
                part_x = x

    if desc_x is None or part_x is None:
        if debug:
            print(f"[STEP4] Page {page} | Missing DESC or PART header")
        return results

    # =====================================================
    # 4️⃣ SORT HEADER COLUMNS
    # =====================================================

    header_x_positions = sorted(header_x_positions)

    desc_index = header_x_positions.index(desc_x)
    part_index = header_x_positions.index(part_x)

    COL_MARGIN = 15

    # =====================================================
    # 5️⃣ COMPUTE DESCRIPTION BOUNDS
    # =====================================================

    if desc_index == 0:
        DESC_LEFT = page_left
    else:
        prev_col = header_x_positions[desc_index - 1]
        DESC_LEFT = prev_col + COL_MARGIN

    if desc_index == len(header_x_positions) - 1:
        DESC_RIGHT = page_right
    else:
        next_col = header_x_positions[desc_index + 1]
        DESC_RIGHT = next_col - COL_MARGIN

    # =====================================================
    # 6️⃣ COMPUTE PART NUMBER BOUNDS
    # =====================================================

    if part_index == 0:
        PART_LEFT = page_left
    else:
        prev_col = header_x_positions[part_index - 1]
        PART_LEFT = prev_col + COL_MARGIN

    if part_index == len(header_x_positions) - 1:
        PART_RIGHT = page_right
    else:
        next_col = header_x_positions[part_index + 1]
        PART_RIGHT = next_col - COL_MARGIN

    if debug:
        print("=" * 80)
        print(f"[STEP4-BOUNDS] Page {page}")
        print(f"DESC X: {desc_x}")
        print(f"PART X: {part_x}")
        print(f"DESC range: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print(f"PART range: {PART_LEFT:.2f} → {PART_RIGHT:.2f}")
        print("=" * 80)

    # =====================================================
    # 7️⃣ HEADER BOTTOM
    # =====================================================
    header_bottom = max(w["bottom"] for w in header_row["words"])

    # =====================================================
    # 8️⃣ EXTRACT DATA ROWS
    # =====================================================
    for row in rows:

        if row["top"] <= header_bottom:
            continue

        words = row["words"]

        pn_words = [
            w for w in words
            if (
                PART_LEFT <= w["x0"] <= PART_RIGHT
                and TABLE_PN_REGEX.search(w["text"])
            )
        ]

        if not pn_words:
            continue

        desc_words = [
            w for w in words
            if DESC_LEFT <= w["x0"] <= DESC_RIGHT
        ]

        desc_words = sorted(desc_words, key=lambda w: w["x0"])
        description = " ".join(w["text"] for w in desc_words).strip()

        if not description:
            continue

        for pn_word in pn_words:
            entry = {
                "page": page,
                "part_no": pn_word["text"],
                "description": description
            }

            if debug:
                entry["trace"] = {
                    "pn_boxes": [{
                        "text": pn_word["text"],
                        "x0": pn_word["x0"],
                        "x1": pn_word["x1"],
                        "top": pn_word["top"],
                        "bottom": pn_word["bottom"],
                    }],
                    "desc_boxes": [
                        {
                            "text": w["text"],
                            "x0": w["x0"],
                            "x1": w["x1"],
                            "top": w["top"],
                            "bottom": w["bottom"],
                        }
                        for w in desc_words
                    ]
                }

            results.append(entry)

    return results

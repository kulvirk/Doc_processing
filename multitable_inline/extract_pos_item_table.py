import re

PN_REGEX = re.compile(
    r"""
    \b(
        \d{5,} |
        \d{2}[A-Z]{2}\d{3,} |
        [A-Z]{2,}\d{3,}[A-Z]? |
        \d{3,}[-/]\d{2,}
    )\b
    """,
    re.VERBOSE
)

def extract_drawing_number_from_rows(rows):

    for row in rows[:10]:
        words = row["words"]

        for i, w in enumerate(words):
            text = w["text"]

            if text.lower().startswith("drawnumber"):

                # Case 1: separate token
                if i + 1 < len(words):
                    value_word = words[i + 1]
                    return value_word["text"], {
                        "text": value_word["text"],
                        "x0": value_word["x0"],
                        "x1": value_word["x1"],
                        "top": value_word["top"],
                        "bottom": value_word["bottom"],
                    }

                # Case 2: merged
                if ":" in text:
                    value = text.split(":")[-1].strip()
                    return value, {
                        "text": value,
                        "x0": w["x0"],
                        "x1": w["x1"],
                        "top": w["top"],
                        "bottom": w["bottom"],
                    }

    return None, None

def extract_pos_item_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])

    if not rows:
        return results
    # -----------------------------------------
    # Extract drawing number (only for this table)
    # -----------------------------------------
    drawing_no, drawing_box = extract_drawing_number_from_rows(rows)

    # -------------------------------------------------
    # 1️⃣ FIND HEADER ROW
    # -------------------------------------------------
    header_row = None

    for row in rows[:15]:
        row_text = " ".join(w["text"].lower() for w in row["words"])
        if (
            "pos" in row_text
            and "qty" in row_text
            and "item name" in row_text
            and "item no" in row_text
        ):
            header_row = row
            break

    if not header_row:
        return results

    if debug:
        print("\n[POS-ITEM HEADER]")
        print([w["text"] for w in header_row["words"]])

    # -------------------------------------------------
    # 2️⃣ GET HEADER X POSITIONS
    # -------------------------------------------------
    item_name_x = None
    item_no_x = None
    qty_x = None

    words = header_row["words"]

    for i, w in enumerate(words):
        text = w["text"].lower()

        if text == "qty":
            qty_x = w["x0"]

        # detect split "item name"
        if text == "item" and i + 1 < len(words):
            next_text = words[i + 1]["text"].lower().replace(".", "")

            if next_text == "name":
                item_name_x = w["x0"]

            if next_text == "no":
                item_no_x = w["x0"]

    if item_name_x is None or item_no_x is None:
        return results

    page_right = max(
        w["x1"]
        for r in rows
        for w in r["words"]
    )

    # -------------------------------------------------
    # 3️⃣ DEFINE COLUMN BOUNDS (AS YOU REQUESTED)
    # -------------------------------------------------

    BIG_MARGIN = 25
    SMALL_MARGIN = 10

    # DESCRIPTION
    DESC_LEFT = qty_x + SMALL_MARGIN if qty_x else item_name_x - BIG_MARGIN
    DESC_RIGHT = item_no_x - BIG_MARGIN

    # PART NUMBER
    PN_LEFT = item_no_x - BIG_MARGIN
    PN_RIGHT = item_no_x + BIG_MARGIN

    if debug:
        print("=" * 80)
        print(f"[POS-ITEM BOUNDS] Page {page}")
        print(f"DESC: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print(f"PN:   {PN_LEFT:.2f} → {PN_RIGHT:.2f}")
        print("=" * 80)

    header_bottom = max(w["bottom"] for w in header_row["words"])

    # -------------------------------------------------
    # 4️⃣ EXTRACT ROWS
    # -------------------------------------------------

    for row in rows:

        if row["top"] <= header_bottom:
            continue

        words = row["words"]

        pn_words = [
            w for w in words
            if (
                PN_LEFT <= w["x0"] <= PN_RIGHT
                and PN_REGEX.search(w["text"])
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
                "description": description,
                "drawing_number": drawing_no or ""
            }
            if debug:
                trace = {
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
            
                # 🔶 ADD DRAWING NUMBER BOX (YELLOW)
                if drawing_box:
                    trace["drawing_box"] = drawing_box
            
                entry["trace"] = trace

            results.append(entry)

    return results

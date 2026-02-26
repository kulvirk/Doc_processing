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
    # Extract drawing number
    # -----------------------------------------
    drawing_no, drawing_box = extract_drawing_number_from_rows(rows)

    # =================================================
    # 🔴 TITLE EXTRACTION (ISOLATED – NO SIDE EFFECTS)
    # =================================================

    table_title = None
    title_words = []

    drawing_row = None

    for r in rows[:8]:
        row_text = " ".join(w["text"].lower() for w in r["words"])
        if "drawingname" in row_text.replace(" ", ""):
            drawing_row = r
            break

    if drawing_row:

        drawing_words = sorted(drawing_row["words"], key=lambda w: w["x0"])

        drawingname_x = None
        right_anchor_x = None

        for w in drawing_words:
            txt = w["text"].lower().replace(" ", "")
            if txt.startswith("drawingname"):
                drawingname_x = w["x0"]
            if txt.startswith("drawingrevision"):
                right_anchor_x = w["x0"]

        if drawingname_x is not None:

            LEFT = drawingname_x - 5
            RIGHT = right_anchor_x - 5 if right_anchor_x else float("inf")

            TOP = max(w["bottom"] for w in drawing_row["words"])
            MAX_LOOKAHEAD = 35

            for r in rows:
                if r["top"] <= TOP:
                    continue
                if r["top"] - TOP > MAX_LOOKAHEAD:
                    break
                for w in r["words"]:
                    if LEFT <= w["x0"] <= RIGHT:
                        title_words.append(w)

            if title_words:
                title_words = sorted(title_words, key=lambda x: (x["top"], x["x0"]))
                table_title = " ".join(w["text"] for w in title_words).strip()

    # =================================================
    # ORIGINAL EXTRACTION LOGIC (UNCHANGED)
    # =================================================

    header_row = None

    for r in rows[:15]:
        row_text = " ".join(w["text"].lower() for w in r["words"])
        if (
            "pos" in row_text
            and "qty" in row_text
            and "item name" in row_text
            and "item no" in row_text
        ):
            header_row = r
            break

    if not header_row:
        return results

    if debug:
        print("\n[POS-ITEM HEADER]")
        print([w["text"] for w in header_row["words"]])

    item_name_x = None
    item_no_x = None
    qty_x = None

    words = header_row["words"]

    for i, w in enumerate(words):
        text = w["text"].lower()

        if text == "qty":
            qty_x = w["x0"]

        if text == "item" and i + 1 < len(words):
            next_text = words[i + 1]["text"].lower().replace(".", "")
            if next_text == "name":
                item_name_x = w["x0"]
            if next_text == "no":
                item_no_x = w["x0"]

    if item_name_x is None or item_no_x is None:
        return results

    BIG_MARGIN = 25
    SMALL_MARGIN = 10

    DESC_LEFT = qty_x + SMALL_MARGIN if qty_x else item_name_x - BIG_MARGIN
    DESC_RIGHT = item_no_x - BIG_MARGIN

    PN_LEFT = item_no_x - BIG_MARGIN
    PN_RIGHT = item_no_x + BIG_MARGIN

    header_bottom = max(w["bottom"] for w in header_row["words"])

    for r in rows:

        if r["top"] <= header_bottom:
            continue

        words = r["words"]

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
                "drawing_number": drawing_no or "",
                "title": table_title or ""
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

                if drawing_box:
                    trace["drawing_box"] = drawing_box

                if table_title and title_words:
                    trace["title_boxes"] = [
                        {
                            "text": w["text"],
                            "x0": w["x0"],
                            "x1": w["x1"],
                            "top": w["top"],
                            "bottom": w["bottom"],
                        }
                        for w in title_words
                    ]

                entry["trace"] = trace

            results.append(entry)

    return results
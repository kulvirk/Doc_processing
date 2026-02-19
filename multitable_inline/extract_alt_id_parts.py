import re

# -------------------------------------------------
# IDENTIFIER REGEXES
# -------------------------------------------------

PART_NO_REGEX = re.compile(
    r"\b(X[A-Z0-9]{6,}|\d{5,}(-\d+)?)\b"
)

ITEM_NO_REGEX = re.compile(
    r"\bXD\d{6,}\b"
)

DRAWING_REF_REGEX = re.compile(
    r"\bD\d{4}[-]?\d+\b"
)

def extract_drawing_number_from_rows(rows):

    for row in rows[:10]:
        words = row["words"]

        for i, w in enumerate(words):
            text = w["text"]

            if text.lower().startswith("drawingno"):

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

# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def _row_text(row):
    return " ".join(w["text"] for w in row["words"]).strip()


# -------------------------------------------------
# MAIN EXTRACTION
# -------------------------------------------------

def extract_alt_id_parts(normalized_table, debug=False):
    """
    STACKED-DESCRIPTION TABLE EXTRACTOR

    Handles BOTH:
    - Part No. / Alternate ID tables
    - Item No. / Item Name tables

    Identifier type is chosen explicitly from header text.

    DEBUG MODE:
    - Emits trace {pn_boxes, desc_boxes} for debug_overlay.py
    """

    results = []

    page = normalized_table["page"]
    rows = normalized_table["rows"]
    drawing_no, drawing_box = extract_drawing_number_from_rows(rows)
    columns = normalized_table.get("columns", [])
    part_col = normalized_table.get("part_col")

    if not rows or part_col is None:
        return results

    # -------------------------------------------------
    # DETERMINE IDENTIFIER TYPE FROM HEADER
    # -------------------------------------------------
    header_text = " ".join(
        w["text"].lower()
        for row in rows[:6]
        for w in row["words"]
    )

    if "item no" in header_text:
        id_regex = ITEM_NO_REGEX
        id_field = "item_no"
        if debug:
            print(f"[ALT-ID] Page {page} | Identifier = ITEM_NO")
    else:
        id_regex = PART_NO_REGEX
        id_field = "part_no"
        if debug:
            print(f"[ALT-ID] Page {page} | Identifier = PART_NO")

    # -------------------------------------------------
    # RIGHT BOUND = DRAWING REFERENCE COLUMN
    # -------------------------------------------------
    drawing_xs = [
        w["x0"]
        for row in rows
        for w in row["words"]
        if DRAWING_REF_REGEX.search(w["text"])
    ]

    RIGHT_BOUND = min(drawing_xs) - 5 if drawing_xs else max(columns)

    # -------------------------------------------------
    # MAIN LOOP
    # -------------------------------------------------
    in_table = False
    i = 0

    while i < len(rows):
        row = rows[i]
        raw = _row_text(row)
        low = raw.lower()

        # ----------------------------
        # WAIT FOR HEADER ROW
        # ----------------------------
        if not in_table:
            if ("part no" in low and "alternate" in low) or ("item no" in low):
                in_table = True
                if debug:
                    print(f"[ALT-ID] >>> TABLE HEADER DETECTED (page {page}) <<<")
            i += 1
            continue

        # ----------------------------
        # IDENTIFIER DETECTION
        # ----------------------------
        id_words = [
            w for w in row["words"]
            if id_regex.fullmatch(w["text"])
            and w["x0"] < RIGHT_BOUND
        ]

        if not id_words:
            i += 1
            continue

        ids = [w["text"] for w in id_words]

        # HARD LEFT BOUND = IDENTIFIER X POSITION
        id_x0 = min(w["x0"] for w in id_words)

        if debug:
            print("\n" + "=" * 80)
            print(f"[ALT-ID][ID ROW] Page {page} | Row {i+1}")
            print(f"[ALT-ID][RAW] {raw}")
            print(f"[ALT-ID] ID_X0 = {id_x0:.1f}")
            print("=" * 80)

        # ----------------------------
        # COLLECT STACKED DESCRIPTION
        # ----------------------------
        desc_words = []
        j = i + 1

        while j < len(rows):
            row_words = [
                w for w in rows[j]["words"]
                if id_x0 <= w["x0"] < RIGHT_BOUND
            ]

            if not row_words:
                j += 1
                continue

            # stop at next identifier row
            if any(id_regex.fullmatch(w["text"]) for w in row_words):
                break

            if debug:
                print(
                    "[ALT-ID]   ↓ DESC ROW:",
                    " ".join(w["text"] for w in row_words)
                )

            desc_words.extend(row_words)
            j += 1

        description = " ".join(
            w["text"]
            for w in sorted(desc_words, key=lambda x: (x["top"], x["x0"]))
        ).strip()

        if debug:
            print(f"[ALT-ID] FINAL DESC = '{description}'")

        # ----------------------------
        # EMIT RESULTS (WITH TRACE)
        # ----------------------------
        for ident in ids:
            entry = {
                "page": page,
                "part_no": ident,
                "description": description,
                "drawing_number": drawing_no or ""
            }
            
            # Optional: keep original meaning if you want
            if id_field == "item_no":
                entry["item_no"] = ident

            # ---- DEBUG TRACE FOR OVERLAY PDF ----
            if debug:
                trace = {
                    "pn_boxes": [
                        {
                            "text": w["text"],
                            "x0": w["x0"],
                            "x1": w["x1"],
                            "top": w["top"],
                            "bottom": w["bottom"],
                        }
                        for w in id_words
                    ],
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

            if debug:
                print(f"[ALT-ID][EMIT] {id_field.upper()}={ident}")

        i += 1

    return results

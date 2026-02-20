import re

PN_REGEX = re.compile(
    r"""
    ^
    (
        \d{4,}-[A-Z0-9]+          |   # 123157-152
        \d{4,}[A-Z]\d+            |   # 5846X001
        \d{4,}[A-Z]{1,3}          |   # 6656PR, 5868A
        \d{4,}                    |   # pure numeric 1315, 7398
        \d{2}[A-Z]{2}\d{3,}       |   # 01PS0002
        [A-Z]{3,}\d{3,}[A-Z]?     |   # OEM2906B
    )
    $
    """,
    re.VERBOSE
)


def extract_split_header_item_part_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])

    if not rows:
        return results

    header_index = None

    # -------------------------------------------------
    # 1️⃣ Detect 2-row split header
    # -------------------------------------------------
    for i in range(len(rows) - 1):

        row1_tokens = {w["text"].lower() for w in rows[i]["words"]}
        row2_tokens = [w["text"].lower() for w in rows[i + 1]["words"]]

        if (
            {"item", "part"}.issubset(row1_tokens)
            and "number" in row2_tokens
            and "qty." in row2_tokens
            and "description" in row2_tokens
        ):
            header_index = i + 1
            break

    if header_index is None:
        return results

    header_row = rows[header_index]

    if debug:
        print("\n[SPLIT HEADER TABLE DETECTED]")
        print([w["text"] for w in header_row["words"]])

    # -------------------------------------------------
    # 2️⃣ Identify anchors in second header row
    # -------------------------------------------------

    number_positions = []
    desc_x = None

    for w in header_row["words"]:
        text = w["text"].lower()

        if text == "number":
            number_positions.append(w)

        if text == "description":
            desc_x = w["x0"]

    if len(number_positions) < 2 or desc_x is None:
        return results

    # Second "Number" is Part Number column
    part_number_word = number_positions[1]

    MARGIN_LEFT = 10
    MARGIN_RIGHT = 20   # give PN enough breathing space
    
    # PART COLUMN
    PART_LEFT = part_number_word["x0"] - MARGIN_LEFT
    PART_RIGHT = part_number_word["x1"] + MARGIN_RIGHT
    
    # DESCRIPTION COLUMN
    DESC_LEFT = PART_RIGHT + 1   # start right after PN column
    DESC_RIGHT = max(
        w["x1"]
        for r in rows
        for w in r["words"]
    )


    header_bottom = max(w["bottom"] for w in header_row["words"])

    if debug:
        print("=" * 80)
        print(f"[SPLIT HEADER BOUNDS] Page {page}")
        print(f"PART: {PART_LEFT:.2f} → {PART_RIGHT:.2f}")
        print(f"DESC: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print("=" * 80)

    # -------------------------------------------------
    # 3️⃣ Extract rows
    # -------------------------------------------------
    for row in rows:

        if row["top"] <= header_bottom:
            continue

        words = row["words"]

        pn_words = [
            w for w in words
            if PART_LEFT <= w["x0"] <= PART_RIGHT
            and PN_REGEX.fullmatch(w["text"])
        ]

        if not pn_words:
            continue

        part_no = pn_words[0]["text"]

        desc_words = [
            w for w in words
            if DESC_LEFT <= w["x0"] <= DESC_RIGHT
        ]

        description = " ".join(
            w["text"] for w in sorted(desc_words, key=lambda x: x["x0"])
        ).strip()

        if not description:
            continue

        entry = {
            "page": page,
            "part_no": part_no,
            "description": description
        }

        if debug:
            entry["trace"] = {
                "pn_boxes": [{
                    "text": pn_words[0]["text"],
                    "x0": pn_words[0]["x0"],
                    "x1": pn_words[0]["x1"],
                    "top": pn_words[0]["top"],
                    "bottom": pn_words[0]["bottom"],
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

    if debug:
        print(f"[SPLIT HEADER TABLE] Extracted {len(results)} rows")

    return results

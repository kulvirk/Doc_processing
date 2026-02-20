import re

BOM_PN_REGEX = re.compile(r"^\d{5,}$")


def extract_single_level_bom(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])

    if not rows:
        return results

    header_row7 = None
    header_row6 = None

    # -------------------------------------------------
    # 1️⃣ Detect header row 7
    # -------------------------------------------------
    for i, row in enumerate(rows[:12]):
        tokens = [w["text"].lower().strip() for w in row["words"]]

        if {"no.", "item", "rev", "description"}.issubset(tokens):
            header_row7 = row
            if i > 0:
                header_row6 = rows[i - 1]
            break

    if not header_row7 or not header_row6:
        return results
    
    if debug:
        print("\n[SINGLE LEVEL BOM HEADER DETECTED]")
        print([w["text"] for w in header_row7["words"]])

    # -------------------------------------------------
    # 🔥 SECTION TITLE DETECTION (SINGLE LEVEL BOM)
    # -------------------------------------------------
    section_title = None
    title_words = []

    header_top = min(w["top"] for w in header_row7["words"])

    for row in rows:
        if row["top"] >= header_top:
            continue

        row_text = " ".join(w["text"] for w in row["words"]).strip()

        if row_text.lower().startswith("description:"):
            section_title = row_text
            title_words = row["words"]
            break

    if debug:
        print(f"[SINGLE BOM TITLE] Page {page} | {section_title}")

    # -------------------------------------------------
    # 2️⃣ Get X anchors
    # -------------------------------------------------
    component_x0 = None
    component_x1 = None
    desc_x = None
    m_x = None

    for w in header_row6["words"]:
        if w["text"].lower() == "component":
            component_x0 = w["x0"]
            component_x1 = w["x1"]

    for w in header_row7["words"]:
        t = w["text"].lower()

        if t == "description":
            desc_x = w["x0"]

        if t == "m":
            m_x = w["x0"]

    if component_x0 is None or desc_x is None or m_x is None:
        return results

    MARGIN = 8

    PN_LEFT = component_x0 - MARGIN
    PN_RIGHT = component_x1 + MARGIN

    DESC_LEFT = desc_x - MARGIN
    DESC_RIGHT = m_x - MARGIN

    header_bottom = max(w["bottom"] for w in header_row7["words"])

    if debug:
        print("=" * 80)
        print(f"[SINGLE BOM BOUNDS] Page {page}")
        print(f"PN:   {PN_LEFT:.2f} → {PN_RIGHT:.2f}")
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
            if PN_LEFT <= w["x0"] <= PN_RIGHT
            and BOM_PN_REGEX.fullmatch(w["text"])
        ]

        if not pn_words:
            continue

        pn_word = pn_words[0]
        part_no = pn_word["text"]

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
            "description": description,
            "title": section_title or ""
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
        
            # 🔴 TITLE BOXES
            if section_title and title_words:
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

    if debug:
        print(f"[SINGLE LEVEL BOM] Extracted {len(results)} rows")

    return results

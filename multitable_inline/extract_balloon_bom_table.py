import re

BOM_PN_REGEX = re.compile(r"^\d{6,}[A-Z]?$")


def extract_balloon_bom_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])

    if not rows:
        return results

    # -------------------------------------------------
    # 1️⃣ Detect 2-row split header
    # -------------------------------------------------
    header_index = None

    for i in range(len(rows) - 1):

        row1 = [w["text"].lower() for w in rows[i]["words"]]
        row2 = [w["text"].lower() for w in rows[i + 1]["words"]]

        if (
            "balloon" in row1
            and "part" in row1
            and "number" in row2
            and "rev" in row2
            and "description" in row2
        ):
            header_index = i + 1
            break

    if header_index is None:
        return results

    header_row = rows[header_index]

    if debug:
        print("\n[BALLOON BOM HEADER DETECTED]")
        print([w["text"] for w in header_row["words"]])

    # -------------------------------------------------
    # 2️⃣ Get column anchors
    # -------------------------------------------------

    part_number_word = None
    rev_word = None
    desc_word = None
    m_word = None

    for w in header_row["words"]:
        text = w["text"].lower()

        if text == "number" and part_number_word is None:
            # second "Number" column is Part Number
            part_number_word = w

        elif text == "rev":
            rev_word = w

        elif text == "description":
            desc_word = w

        elif text == "m":
            m_word = w

    if not part_number_word or not rev_word or not desc_word:
        return results

    MARGIN = 5


    # -------------------------------------------------
    # 🔥 SECTION TITLE DETECTION (BALLOON BOM)
    # -------------------------------------------------
    section_title = None
    title_words = []

    header_top = min(w["top"] for w in header_row["words"])

    for row in rows:

        row_top = row["top"]

        # Only look above table header
        if row_top >= header_top:
            continue

        words = row["words"]
        row_text = " ".join(w["text"] for w in words).strip()

        if row_text.lower().startswith("description:"):
            section_title = row_text
            title_words = words
            break

    if debug:
        print(f"[BALLOON TITLE] Page {page} | {section_title}")
    # -------------------------------------------------
    # 3️⃣ Column bounds (your exact logic)
    # -------------------------------------------------

    # PART NUMBER
    PN_LEFT = part_number_word["x0"] - MARGIN
    PN_RIGHT = rev_word["x0"] - MARGIN

    # DESCRIPTION
    DESC_LEFT = rev_word["x0"] + MARGIN
    DESC_RIGHT = m_word["x0"] - MARGIN if m_word else max(
        w["x1"] for r in rows for w in r["words"]
    )

    header_bottom = max(w["bottom"] for w in header_row["words"])

    if debug:
        print("=" * 80)
        print(f"[BALLOON BOM BOUNDS] Page {page}")
        print(f"PN:   {PN_LEFT:.2f} → {PN_RIGHT:.2f}")
        print(f"DESC: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print("=" * 80)

    # -------------------------------------------------
    # 4️⃣ Extract rows
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
        print(f"[BALLOON BOM] Extracted {len(results)} rows")

    return results


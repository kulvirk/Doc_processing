from multitable_inline.patterns import PART_NO_REGEX

def extract_simple_2col_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table["rows"]
    columns = sorted(normalized_table.get("columns", []))
    part_index = normalized_table.get("part_col")

    if not rows or part_index is None or not columns:
        return results

    page_left = min(w["x0"] for row in rows for w in row["words"])
    page_right = max(w["x1"] for row in rows for w in row["words"])

    # --------------------------------------------------
    # 1️⃣ Find header row and exact x of "Description"
    # --------------------------------------------------
    header_row = None
    desc_header_x = None

    for row in rows:
        row_text = " ".join(w["text"].lower() for w in row["words"])
        if "part" in row_text and "description" in row_text:
            header_row = row
            for w in row["words"]:
                if "description" in w["text"].lower():
                    desc_header_x = w["x0"]
                    break
            break

    if header_row is None or desc_header_x is None:
        if debug:
            print(f"[SIMPLE_2COL] Page {page} | Header not found")
        return results

    COL_MARGIN = 6  # tighter margin

    # --------------------------------------------------
    # 2️⃣ PART column bounds (pure structural)
    # --------------------------------------------------
    if part_index == 0:
        PART_LEFT = page_left
    else:
        PART_LEFT = columns[part_index - 1] + COL_MARGIN

    # Slightly expand right side to fully include PN text
    if part_index == len(columns) - 1:
        PART_RIGHT = page_right
    else:
        PART_RIGHT = columns[part_index + 1] - (COL_MARGIN // 2)

    # --------------------------------------------------
    # 3️⃣ DESC bounds (strictly from header x-position)
    # --------------------------------------------------
    DESC_LEFT = desc_header_x
    DESC_RIGHT = page_right

    if debug:
        print("=" * 80)
        print(f"[SIMPLE_2COL BOUNDS] Page {page}")
        print(f"PART range: {PART_LEFT:.2f} → {PART_RIGHT:.2f}")
        print(f"DESC range: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print("=" * 80)

    header_bottom = max(w["bottom"] for w in header_row["words"])

    # --------------------------------------------------
    # 4️⃣ Extract rows
    # --------------------------------------------------
    for row in rows:

        if row["top"] <= header_bottom:
            continue

        pn_words = [
            w for w in row["words"]
            if PART_LEFT <= w["x0"] <= PART_RIGHT
        ]

        if not pn_words:
            continue

        # Only take first token in PN column
        pn_word = sorted(pn_words, key=lambda w: w["x0"])[0]
        pn = pn_word["text"]

        desc_words = [
            w for w in row["words"]
            if DESC_LEFT <= w["x0"] <= DESC_RIGHT
        ]

        desc_words = sorted(desc_words, key=lambda w: w["x0"])
        description = " ".join(w["text"] for w in desc_words).strip()

        if not description:
            continue

        entry = {
            "page": page,
            "part_no": pn,
            "description": description
        }

        # Debug overlay support
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

    if debug:
        print(f"[SIMPLE_2COL] Extracted {len(results)} rows")

    return results



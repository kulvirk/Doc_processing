import re

SIMPLE3_PN_REGEX = re.compile(
    r"""
    ^
    (
        \d{2}-\d{6}                           |   # 01-025190
        [A-Z0-9]+(?:[.-][A-Z0-9]+)+           |   # PTU-16.5A-FE-HYD
        \d{5,}                                |   # pure numeric
        \d{2}[A-Z]{2}\d{3,}                   |
        [A-Z]{2,}\d{3,}[A-Z]?                 |
        \d{3,}[-/]\d{2,}
    )
    $
    """,
    re.VERBOSE
)


def extract_simple_3col_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])

    if not rows:
        return results

    # -------------------------------------------------
    # 1️⃣ FIND HEADER ROW
    # -------------------------------------------------
    header_row = None

    for row in rows[:6]:
        texts = [w["text"].upper() for w in row["words"]]

        if any("DESC" in t for t in texts) and any(
            any(k in t for k in ["PART", "ITEM", "MATERIAL", "ARTICLE"])
            for t in texts
        ):
            header_row = row
            break

    if not header_row:
        return results

    if debug:
        print(f"[SIMPLE-3COL] Header row: {[w['text'] for w in header_row['words']]}")

    header_bottom = max(w["bottom"] for w in header_row["words"])

    page_right = max(
        w["x1"]
        for r in rows
        for w in r["words"]
    )

    MARGIN = 5

    # -------------------------------------------------
    # 2️⃣ Sort header words left → right
    # -------------------------------------------------
    header_words = sorted(header_row["words"], key=lambda w: w["x0"])

    # -------------------------------------------------
    # 3️⃣ Build PART → DESC blocks
    # -------------------------------------------------
    blocks = []

    for i, w in enumerate(header_words):

        t = w["text"].upper()

        if any(k in t for k in ["PART", "ITEM", "MATERIAL", "ARTICLE"]):

            blocks.append(w)

    if not blocks:
        return results

    # -------------------------------------------------
    # 4️⃣ Process each block independently
    # -------------------------------------------------
    for block_index, pn_header in enumerate(blocks):

        # Determine next block boundary
        next_block_x = page_right

        for other in blocks:
            if other["x0"] > pn_header["x0"]:
                next_block_x = other["x0"]
                break

        # ----------------------------
        # 🔥 CORRECT GEOMETRY FIX
        # ----------------------------
        pn_left = pn_header["x0"] - MARGIN

        # PART column ends near its own header width
        pn_right = pn_header["x1"] + 15

        # DESCRIPTION begins right after PART column
        desc_left = pn_right + 2

        desc_right = next_block_x - 4

        if debug:
            print("=" * 80)
            print(f"[BLOCK {block_index+1}]")
            print(f"PN:   {pn_left:.2f} → {pn_right:.2f}")
            print(f"DESC: {desc_left:.2f} → {desc_right:.2f}")
            print("=" * 80)

        current_part = None
        current_desc_words = []
        current_pn_words = []

        # -------------------------------------------------
        # 5️⃣ Extract rows
        # -------------------------------------------------
        for row in rows:

            if row["top"] <= header_bottom - 1:
                continue

            words = row["words"]

            pn_band_words = [
                w for w in words
                if pn_left <= w["x0"] <= pn_right
            ]

            pn_band_words = sorted(pn_band_words, key=lambda w: w["x0"])

            numeric_join = "".join(
                w["text"] for w in pn_band_words
                if w["text"].isdigit()
            )

            pn_value = None

            if len(numeric_join) >= 6:
                pn_value = numeric_join
            else:
                for w in pn_band_words:
                    if SIMPLE3_PN_REGEX.fullmatch(w["text"]):
                        pn_value = w["text"]
                        break

            pn_used_words = []

            if len(numeric_join) >= 6:
                pn_used_words = [w for w in pn_band_words if w["text"].isdigit()]
            else:
                for w in pn_band_words:
                    if SIMPLE3_PN_REGEX.fullmatch(w["text"]):
                        pn_used_words = [w]
                        break

            desc_words = [
                w for w in words
                if desc_left <= w["x0"] <= desc_right
            ]

            if pn_value:

                if current_part and current_desc_words:
                    description = " ".join(
                        w["text"]
                        for w in sorted(current_desc_words, key=lambda x: (x["top"], x["x0"]))
                    ).strip()

                    entry = {
                        "page": page,
                        "part_no": current_part,
                        "description": description
                    }

                    if debug:
                        entry["trace"] = {

                            "pn_boxes": [
                                {
                                    "text": w["text"],
                                    "x0": w["x0"],
                                    "x1": w["x1"],
                                    "top": w["top"],
                                    "bottom": w["bottom"],
                                }
                                for w in pn_used_words
                            ],
                            
                            "desc_boxes": [
                                {
                                    "text": w["text"],
                                    "x0": w["x0"],
                                    "x1": w["x1"],
                                    "top": w["top"],
                                    "bottom": w["bottom"],
                                }
                                for w in current_desc_words
                            ]
                        }

                    results.append(entry)

                current_part = pn_value
                current_desc_words = desc_words.copy()
                current_pn_words = pn_band_words.copy()

            elif desc_words and current_part:

                # Stop extending if vertical gap too large
                last_top = max(w["top"] for w in current_desc_words) if current_desc_words else None
            
                if last_top is not None:
                    gap = row["top"] - last_top
            
                    if gap > 18:
                        # DO NOT reset current_part
                        # Just stop extending description
                        continue
            
                current_desc_words.extend(desc_words)

        if current_part and current_desc_words:
            description = " ".join(
                w["text"]
                for w in sorted(current_desc_words, key=lambda x: (x["top"], x["x0"]))
            ).strip()

            entry = {
                "page": page,
                "part_no": current_part,
                "description": description
            }

            results.append(entry)

    if debug:
        print(f"[SIMPLE-3COL] Extracted {len(results)} rows")

    return results

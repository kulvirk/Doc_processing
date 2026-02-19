"""
SIMPLE 3-COLUMN HEADER-BASED EXTRACTOR

Uses:
- Header detection (PART / ITEM / MATERIAL + DESC)
- X-coordinate bands only
- No regex
- No structure validation
"""

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

    # -------------------------------------------------
    # 2️⃣ IDENTIFY PN & DESC HEADER WORDS
    # -------------------------------------------------
    pn_header = None
    desc_header = None

    for w in header_row["words"]:
        t = w["text"].upper()

        if any(k in t for k in ["PART", "ITEM", "MATERIAL", "ARTICLE"]):
            pn_header = w

        if "DESC" in t or "NAME" in t:
            desc_header = w

    if not pn_header or not desc_header:
        return results

    header_bottom = max(w["bottom"] for w in header_row["words"])

    # -------------------------------------------------
    # 3️⃣ DEFINE COLUMN RANGES (WIDE SAFE MARGINS)
    # -------------------------------------------------
    page_right = max(
        w["x1"]
        for r in rows
        for w in r["words"]
    )

    PN_LEFT_MARGIN = 25
    PN_RIGHT_GAP = 15
    DESC_LEFT_MARGIN = 10

    pn_left = pn_header["x0"] - PN_LEFT_MARGIN
    pn_right = desc_header["x0"] - PN_RIGHT_GAP

    desc_left = desc_header["x0"] - DESC_LEFT_MARGIN
    desc_right = page_right

    if debug:
        print(f"[SIMPLE-3COL] PN range: {pn_left:.2f} → {pn_right:.2f}")
        print(f"[SIMPLE-3COL] DESC range: {desc_left:.2f} → {desc_right:.2f}")

    # -------------------------------------------------
    # 4️⃣ EXTRACT USING X-COORD ONLY
    # -------------------------------------------------
    current_part = None
    current_desc_words = []
    current_pn_words = []

    for row in rows:

        if row["top"] <= header_bottom:
            continue

        words = row["words"]

        pn_words = [
            w for w in words
            if pn_left <= w["x0"] <= pn_right
        ]

        desc_words = [
            w for w in words
            if desc_left <= w["x0"] <= desc_right
        ]

        if pn_words:

            # Emit previous
            if current_part and current_desc_words:
                description = " ".join(
                    w["text"]
                    for w in sorted(current_desc_words, key=lambda x: (x["top"], x["x0"]))
                ).strip()

                results.append({
                    "page": page,
                    "part_no": current_part,
                    "description": description,
                    "trace": {
                        "pn_boxes": current_pn_words,
                        "desc_boxes": current_desc_words
                    } if debug else {}
                })

            current_part = " ".join(
                w["text"]
                for w in sorted(pn_words, key=lambda x: x["x0"])
            ).strip()

            current_desc_words = desc_words.copy()
            current_pn_words = pn_words.copy()

        elif desc_words and current_part:
            current_desc_words.extend(desc_words)

    # Emit last
    if current_part and current_desc_words:
        description = " ".join(
            w["text"]
            for w in sorted(current_desc_words, key=lambda x: (x["top"], x["x0"]))
        ).strip()

        results.append({
            "page": page,
            "part_no": current_part,
            "description": description,
            "trace": {
                "pn_boxes": current_pn_words,
                "desc_boxes": current_desc_words
            } if debug else {}
        })

    if debug:
        print(f"[SIMPLE-3COL] Extracted {len(results)} rows")

    return results

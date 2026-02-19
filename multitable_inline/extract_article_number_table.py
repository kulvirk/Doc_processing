import re

ARTICLE_PN_REGEX = re.compile(r"\b[A-Z]\d+-\d{4}-\d{3,}\b")


def extract_article_number_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])
    # -------------------------------------------------
    # FOOTER LIMIT (IGNORE TITLE BLOCK / SHEET INFO)
    # -------------------------------------------------
    all_words = [w for r in rows for w in r["words"]]
    page_bottom = max(w["bottom"] for w in all_words)
    
    FOOTER_Y_LIMIT = page_bottom * 0.92


    if not rows:
        return results

    # -------------------------------------------------
    # 1️⃣ FIND HEADER ROW (STRICT SIGNATURE)
    # -------------------------------------------------
    header_row = None

    for row in rows[:15]:
        row_text = " ".join(
            w["text"].lower().replace(".", "")
            for w in row["words"]
        )

        if (
            "article" in row_text
            and "number" in row_text
            and "description" in row_text
            and "no" in row_text
            and "certificate" in row_text
        ):
            header_row = row
            break

    if not header_row:
        return results

    if debug:
        print("\n[ARTICLE HEADER]")
        print([w["text"] for w in header_row["words"]])

    # Ensure left-to-right order
    header_words = sorted(header_row["words"], key=lambda w: w["x0"])

    # -------------------------------------------------
    # 2️⃣ DETERMINE COLUMN BOUNDS
    # -------------------------------------------------
    article_x0 = None
    number_x1 = None
    no_x0 = None

    for i, w in enumerate(header_words):
        text = w["text"].lower().replace(".", "")

        if text == "article":
            article_x0 = w["x0"]

        if text == "number" and article_x0 is not None:
            number_x1 = w["x1"]

        if text == "no":
            no_x0 = w["x0"]

    if not article_x0 or not number_x1 or not no_x0:
        return results

    MARGIN = 8

    PN_LEFT = article_x0 - MARGIN
    PN_RIGHT = number_x1 + MARGIN

    DESC_LEFT = PN_RIGHT + MARGIN
    DESC_RIGHT = no_x0 - MARGIN

    if debug:
        print("=" * 80)
        print(f"[ARTICLE BOUNDS] Page {page}")
        print(f"PN:   {PN_LEFT:.2f} → {PN_RIGHT:.2f}")
        print(f"DESC: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print("=" * 80)

    header_bottom = max(w["bottom"] for w in header_words)

    # -------------------------------------------------
    # 3️⃣ EXTRACT ROWS
    # -------------------------------------------------
    current_part = None
    current_desc_words = []
    current_pn_words = []

    for row in rows:

        # Skip header
        if row["top"] <= header_bottom:
            continue
    
        # Skip footer region
        if row["top"] >= FOOTER_Y_LIMIT:
            continue

        words = row["words"]

        pn_words = [
            w for w in words
            if PN_LEFT <= w["x0"] <= PN_RIGHT
            and ARTICLE_PN_REGEX.search(w["text"])
        ]

        desc_words = [
            w for w in words
            if DESC_LEFT <= w["x0"] <= DESC_RIGHT
        ]

        # NEW ROW
        if pn_words:

            # Emit previous
            if current_part and current_desc_words:

                description = " ".join(
                    w["text"]
                    for w in sorted(
                        current_desc_words,
                        key=lambda x: (x["top"], x["x0"])
                    )
                ).strip()

                entry = {
                    "page": page,
                    "part_no": current_part,
                    "description": description,
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
                            for w in current_pn_words.copy()
                        ],
                        "desc_boxes": [
                            {
                                "text": w["text"],
                                "x0": w["x0"],
                                "x1": w["x1"],
                                "top": w["top"],
                                "bottom": w["bottom"],
                            }
                            for w in current_desc_words.copy()
                        ],
                    }

                results.append(entry)

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
            for w in sorted(
                current_desc_words,
                key=lambda x: (x["top"], x["x0"])
            )
        ).strip()

        entry = {
            "page": page,
            "part_no": current_part,
            "description": description,
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
                    for w in current_pn_words.copy()
                ],
                "desc_boxes": [
                    {
                        "text": w["text"],
                        "x0": w["x0"],
                        "x1": w["x1"],
                        "top": w["top"],
                        "bottom": w["bottom"],
                    }
                    for w in current_desc_words.copy()
                ],
            }

        results.append(entry)

    if debug:
        print(f"[ARTICLE TABLE] Extracted {len(results)} rows")

    return results

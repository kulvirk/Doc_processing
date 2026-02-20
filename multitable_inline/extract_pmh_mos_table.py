def extract_pmh_mos_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])

    if not rows:
        return results

    # -------------------------------------------------
    # 1️⃣ Detect header row
    # -------------------------------------------------
    header_row = None
    header_index = None

    for i, row in enumerate(rows[:12]):
        tokens = [w["text"].lower() for w in row["words"]]

        if (
            "item" in tokens
            and "qty" in tokens
            and "description" in tokens
            and ("pmh" in tokens or "mos" in tokens)
            and "part" in tokens
            and "no" in tokens
        ):
            header_row = row
            header_index = i
            break

    if not header_row:
        return results

    header_top = min(w["top"] for w in header_row["words"])
    header_bottom = max(w["bottom"] for w in header_row["words"])

    # -------------------------------------------------
    # 2️⃣ 🔥 SECTION TITLE DETECTION (FIXED VERSION)
    # -------------------------------------------------
    section_title = None
    title_words = []

    for i in range(header_index - 1, -1, -1):

        row = rows[i]
        words = row["words"]

        if not words:
            continue

        # Sort left → right
        words_sorted = sorted(words, key=lambda w: w["x0"])

        candidate_words = []

        for w in words_sorted:

            txt = w["text"].strip()

            # Stop at numeric
            if any(c.isdigit() for c in txt):
                break

            # Stop at lowercase-dominant word
            if txt.lower() == txt and txt.upper() != txt:
                break

            # Stop at "Total"
            if txt.lower().startswith("total"):
                break

            candidate_words.append(w)

        if not candidate_words:
            continue

        candidate_text = " ".join(w["text"] for w in candidate_words).strip()

        # Validation
        if len(candidate_text) < 5 or len(candidate_text) > 60:
            continue

        alpha_ratio = sum(c.isalpha() for c in candidate_text) / len(candidate_text)
        if alpha_ratio < 0.8:
            continue

        word_count = len(candidate_text.split())
        if word_count > 6:
            continue

        section_title = candidate_text
        title_words = candidate_words
        break

    if debug and section_title:
        print(f"[PMH TITLE] Page {page} | {section_title}")

    # -------------------------------------------------
    # 3️⃣ Identify X anchors
    # -------------------------------------------------
    desc_x = None
    pn_x = None
    material_x = None

    for w in header_row["words"]:
        t = w["text"].lower()

        if t == "description":
            desc_x = w["x0"]

        if t in {"pmh", "mos"}:
            pn_x = w["x0"]

        if t == "material":
            material_x = w["x0"]

    if desc_x is None or pn_x is None:
        return results

    page_right = max(
        w["x1"]
        for r in rows
        for w in r["words"]
    )

    MARGIN = 10

    DESC_LEFT = desc_x - 2
    DESC_RIGHT = pn_x - MARGIN

    PN_LEFT = pn_x - 2
    PN_RIGHT = material_x - MARGIN if material_x else page_right

    # -------------------------------------------------
    # 4️⃣ Collect all words
    # -------------------------------------------------
    all_words = [w for r in rows for w in r["words"]]

    # -------------------------------------------------
    # 5️⃣ Detect PN anchors
    # -------------------------------------------------
    pn_words_all = [
        w for w in all_words
        if (
            w["top"] > header_bottom
            and PN_LEFT <= w["x0"] <= PN_RIGHT
        )
    ]

    pn_words_all = sorted(pn_words_all, key=lambda w: w["top"])

    if not pn_words_all:
        return results

    # -------------------------------------------------
    # 6️⃣ Extract description using Y-vicinity
    # -------------------------------------------------
    Y_THRESHOLD = 20

    for pn_w in pn_words_all:

        pn_top = pn_w["top"]

        desc_words = [
            w for w in all_words
            if (
                abs(w["top"] - pn_top) <= Y_THRESHOLD
                and DESC_LEFT <= w["x0"] <= DESC_RIGHT
            )
        ]

        desc_words = sorted(desc_words, key=lambda x: (x["top"], x["x0"]))

        description = " ".join(w["text"] for w in desc_words).strip()

        if not description:
            continue

        entry = {
            "page": page,
            "part_no": pn_w["text"],
            "description": description,
            "title": section_title or ""
        }

        if debug:
            entry["trace"] = {
                "pn_boxes": [{
                    "text": pn_w["text"],
                    "x0": pn_w["x0"],
                    "x1": pn_w["x1"],
                    "top": pn_w["top"],
                    "bottom": pn_w["bottom"],
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

            # 🔴 Title overlay support
            if section_title and title_words:
                entry["trace"]["title_boxes"] = [
                    {
                        "text": w["text"],
                        "x0": w["x0"],
                        "x1": w["x1"],
                        "top": w["top"],
                        "bottom": w["bottom"],
                    }
                    for w in title_words
                ]

        results.append(entry)

    return results
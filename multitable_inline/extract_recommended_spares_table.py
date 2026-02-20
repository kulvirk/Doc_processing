import re

PN_REGEX = re.compile(r"^[0-9A-Z\-]+$")

def extract_recommended_spares_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])

    if not rows:
        return results

    # -------------------------------------------------
    # 1️⃣ Detect header row
    # -------------------------------------------------
    header_index = None

    for i, row in enumerate(rows):
        tokens = [w["text"] for w in row["words"]]

        if tokens == ['Parts', 'List', 'Item', 'Qty', 'Description', 'PMH', 'Part', 'No']:
            header_index = i
            break

    if header_index is None:
        return results

    header_row = rows[header_index]

    if debug:
        print("\n[RECOMMENDED SPARES HEADER DETECTED]")
        print([w["text"] for w in header_row["words"]])

    # -------------------------------------------------
    # 2️⃣ 🔥 SECTION TITLE DETECTION (FINAL FIX)
    # -------------------------------------------------
    section_title = None
    title_words = []

    for i in range(header_index - 1, -1, -1):

        row = rows[i]
        words = row["words"]

        if not words:
            continue

        candidate_text = " ".join(w["text"] for w in words).strip()

        # Skip small labels
        if candidate_text.lower() in {"unit", "weight", "(kg)"}:
            continue

        # Skip metadata rows
        if ":" in candidate_text:
            continue

        # Must be mostly uppercase words
        if candidate_text.upper() != candidate_text:
            continue

        # Must not contain digits
        if any(c.isdigit() for c in candidate_text):
            continue

        # Must have at least 2 words
        if len(candidate_text.split()) < 2:
            continue

        section_title = candidate_text
        title_words = words
        break

    if debug:
        print(f"[RECOMMENDED TITLE] Page {page} | {section_title}")
        
    # -------------------------------------------------
    # 3️⃣ Column anchors
    # -------------------------------------------------
    desc_x = None
    pmh_x = None

    for w in header_row["words"]:
        if w["text"] == "Description":
            desc_x = w["x0"]
        if w["text"] == "PMH":
            pmh_x = w["x0"]

    if desc_x is None or pmh_x is None:
        return results

    MARGIN = 10

    DESC_LEFT = desc_x - MARGIN
    DESC_RIGHT = pmh_x - MARGIN
    PN_LEFT = pmh_x - MARGIN

    # Find weight column for right bound
    weight_x = None
    for row in rows[header_index + 1: header_index + 4]:
        for w in row["words"]:
            if "weight" in w["text"].lower():
                weight_x = w["x0"]
                break
        if weight_x:
            break

    page_right = max(
        w["x1"] for r in rows for w in r["words"]
    )

    PN_RIGHT = weight_x - MARGIN if weight_x else page_right

    header_bottom = max(w["bottom"] for w in header_row["words"])

    if debug:
        print("=" * 80)
        print(f"[RECOMMENDED SPARES BOUNDS] Page {page}")
        print(f"DESC: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print(f"PN:   {PN_LEFT:.2f} → {PN_RIGHT:.2f}")
        print("=" * 80)

    # -------------------------------------------------
    # 4️⃣ Find PN words below header
    # -------------------------------------------------
    all_words = [w for r in rows for w in r["words"]]

    pn_words_all = [
        w for w in all_words
        if (
            w["top"] > header_bottom
            and PN_LEFT <= w["x0"] <= PN_RIGHT
            and PN_REGEX.fullmatch(w["text"])
        )
    ]

    pn_words_all = sorted(pn_words_all, key=lambda w: w["top"])

    if debug:
        print(f"[RECOMMENDED SPARES] Found {len(pn_words_all)} PN anchors")

    # -------------------------------------------------
    # 5️⃣ Extract description
    # -------------------------------------------------
    Y_THRESHOLD = 12

    for pn_w in pn_words_all:

        pn_top = pn_w["top"]

        desc_words = [
            w for w in all_words
            if (
                abs(w["top"] - pn_top) <= Y_THRESHOLD
                and DESC_LEFT <= w["x0"] <= DESC_RIGHT
            )
        ]

        desc_words = sorted(desc_words, key=lambda x: (round(x["top"], 1), x["x0"]))

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
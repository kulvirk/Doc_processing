import re


# Industrial MARK pattern like 15N642, 26C363, etc.
MARK_PN_REGEX = re.compile(
    r"\b(?:[0-9]{1,3}[A-Z][0-9]{2,4}|\d{6})\b"
)



def extract_mark_table(normalized_table, debug=False):
    """
    SPECIAL HANDLER FOR TABLES WITH:

    DWG NO | REV | QTY | DESCRIPTION | MARK | WEIGHT

    Extraction rule:
        part_no = MARK column
        description = DESCRIPTION column
    """

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])
    columns = normalized_table.get("columns", [])

    if not rows:
        return results

    # -------------------------------------------------
    # 1️⃣ DETECT HEADER WORDS
    # -------------------------------------------------
    mark_word = None
    desc_word = None

    for row in rows[:15]:
        for w in row["words"]:
            t = w["text"].strip().lower()
            if t == "mark":
                mark_word = w
            if t == "description":
                desc_word = w

    if not mark_word or not desc_word:
        if debug:
            print(f"[MARK] Page {page} | Header words not found")
        return results

    mark_x = mark_word["x0"]
    desc_x = desc_word["x0"]

    header_y = max(mark_word["bottom"], desc_word["bottom"])

    # -------------------------------------------------
    # 2️⃣ DEFINE COLUMN RANGES
    # -------------------------------------------------

    # MARK column (wide tolerance)
    MARK_TOL = 60
    mark_col_range = (mark_x - MARK_TOL, mark_x + MARK_TOL)

    # DESCRIPTION column:
    # If structural columns exist, use column geometry.
    # Otherwise fallback to header-based geometry.

    # -------------------------------------------------
    # DESCRIPTION COLUMN BASED ON QTY → MARK
    # -------------------------------------------------
    
    qty_word = None
    
    for row in rows[:15]:
        for w in row["words"]:
            if w["text"].strip().lower() == "qty":
                qty_word = w
                break
    
    if qty_word:
        desc_left = qty_word["x0"] + 10
    else:
        # fallback if QTY not found
        desc_left = desc_word["x0"] - 50
    
    desc_right = mark_word["x0"] - 20
    
    desc_col_range = (desc_left, desc_right)


    if debug:
        print("=" * 80)
        print(f"[MARK] Page {page}")
        print(f"[MARK] mark_x: {mark_x}")
        print(f"[MARK] desc_x: {desc_x}")
        print(f"[MARK] Columns detected: {columns}")
        print(f"[MARK] MARK range: {mark_col_range}")
        print(f"[MARK] DESC range: {desc_col_range}")
        print(f"[MARK] Header Y cutoff: {header_y}")
        print("=" * 80)


    # -------------------------------------------------
    # 🔥 SECTION TITLE DETECTION (MARK TABLE)
    # -------------------------------------------------
    section_title = None
    title_words = []

    header_top = header_y

    # Collect candidate words in DESC column above header
    candidate_words = [
        w for row in rows
        for w in row["words"]
        if (
            w["bottom"] < header_top
            and desc_col_range[0] <= w["x0"] <= desc_col_range[1]
        )
    ]

    # Sort top → bottom
    candidate_words = sorted(candidate_words, key=lambda x: (x["top"], x["x0"]))

    if candidate_words:

        # Group into lines
        lines = {}
        for w in candidate_words:
            key = round(w["top"], 1)
            lines.setdefault(key, []).append(w)

        sorted_lines = sorted(lines.items(), key=lambda x: x[0])

        collected_words = []
        last_top = None
        MAX_GAP = 20

        for top, ws in sorted_lines:

            if last_top is not None:
                if top - last_top > MAX_GAP:
                    break

            collected_words.extend(ws)
            last_top = top

        if collected_words:
            section_title = " ".join(
                w["text"] for w in sorted(collected_words, key=lambda x: (x["top"], x["x0"]))
            ).strip()

            title_words = collected_words

    if debug:
        print(f"[MARK TITLE] Page {page} | {section_title}")

    # -------------------------------------------------
    # 3️⃣ COLLECT ALL WORDS BELOW HEADER
    # -------------------------------------------------
    all_words = [
        w
        for row in rows
        for w in row["words"]
        if w["top"] > header_y
    ]

    # -------------------------------------------------
    # 4️⃣ FIND ALL MARK WORDS FIRST
    # -------------------------------------------------
    mark_words = [
        w for w in all_words
        if (
            mark_col_range[0] <= w["x0"] <= mark_col_range[1]
            and MARK_PN_REGEX.search(w["text"])
        )
    ]

    mark_words = sorted(mark_words, key=lambda x: x["top"])

    if not mark_words:
        return results
        
    # -------------------------------------------------
    # 5️⃣ EXTRACT USING CONTROLLED VERTICAL BANDS
    # -------------------------------------------------
    
    MAX_LINE_GAP = 18   # adjust if needed (row spacing tolerance)
    MAX_TOTAL_HEIGHT = 80  # safety cap to prevent runaway capture
    
    for i, mark_w in enumerate(mark_words):
    
        part_no = mark_w["text"]
        current_top = mark_w["top"]
    
        # Define upper boundary
        if i + 1 < len(mark_words):
            next_top = mark_words[i + 1]["top"]
        else:
            next_top = current_top + MAX_TOTAL_HEIGHT
    
        # Collect candidate words in DESC column inside vertical band
        band_words = [
            w for w in all_words
            if (
                current_top - 5 <= w["top"] < next_top - 5
                and desc_col_range[0] <= w["x0"] <= desc_col_range[1]
            )
        ]
    
        # Sort by vertical position
        band_words = sorted(band_words, key=lambda x: (x["top"], x["x0"]))
    
        # ---------------------------------------------
        # NEW: Stop if vertical gap too large
        # ---------------------------------------------
        desc_words = []
        last_top = None
    
        for w in band_words:
            if last_top is None:
                desc_words.append(w)
                last_top = w["top"]
                continue
    
            gap = w["top"] - last_top
    
            if gap > MAX_LINE_GAP:
                break  # real row break detected
    
            desc_words.append(w)
            last_top = w["top"]
    
        description = " ".join(w["text"] for w in desc_words).strip()
    
        if not description:
            continue
    
        if debug:
            print("\n[MARK][ROW]")
            print(f"PN = {part_no}")
            print(f"DESC = {description}")

        entry = {
            "page": page,
            "part_no": part_no,
            "description": description,
            "title": section_title or ""
        }

        if debug:
            trace = {
                "pn_boxes": [{
                    "text": mark_w["text"],
                    "x0": mark_w["x0"],
                    "x1": mark_w["x1"],
                    "top": mark_w["top"],
                    "bottom": mark_w["bottom"],
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
    
    return results

from multitable_inline.patterns import PART_NO_REGEX, X_TOL, Y_TOL


def is_structural_word(w):
    t = w["text"]
    return (
        t.isdigit() or
        t.upper() in {"REF", "NS"} or
        PART_NO_REGEX.search(t)
    )
def _merge_fragmented_words(row_words, gap_threshold=6):
    """
    Merge adjacent word fragments that belong to the same visual word.
    """
    if not row_words:
        return row_words

    merged = []
    current = row_words[0].copy()

    for w in row_words[1:]:
        gap = w["x0"] - current["x1"]

        # If small horizontal gap → merge
        if gap >= 0 and gap <= gap_threshold:
            current["text"] += w["text"]
            current["x1"] = w["x1"]
            current["bottom"] = max(current["bottom"], w["bottom"])
        else:
            merged.append(current)
            current = w.copy()

    merged.append(current)
    return merged


# -------------------------------------------------
# NEW: Detect table title using font dominance
# -------------------------------------------------
def detect_table_title(words, table_top_y):
    """
    Title = largest-font text ABOVE the table.
    """
    candidates = []

    for w in words:
        # Only consider text ABOVE table
        if w["bottom"] >= table_top_y:
            continue

        text = w["text"].strip()
        if not text:
            continue

        # Ignore very short labels like Qty, (a), etc.
        if len(text) <= 5:
            continue

        # Mostly alphabetic (titles are words, not numbers)
        alpha_ratio = sum(c.isalpha() for c in text) / len(text)
        if alpha_ratio < 0.6:
            continue

        candidates.append(w)

    if not candidates:
        return None

    # Group words into lines by Y proximity
    lines = {}
    for w in candidates:
        y = round(w["top"] / 5) * 5
        lines.setdefault(y, []).append(w)

    scored = []
    for line_words in lines.values():
        line_text = " ".join(w["text"] for w in line_words)
        avg_size = sum(w.get("size", 0) for w in line_words) / len(line_words)
        scored.append((avg_size, line_text))

    # Largest font wins
    scored.sort(reverse=True)
    return scored[0][1]


def normalize_table(table_candidate, debug=False):
    words = table_candidate["words"]
    page = table_candidate["page"]

    if not words:
        return {
            "page": page,
            "columns": [],
            "rows": [],
            "part_col": None,
            "table_title": None,
        }

    # -------------------------------------------------
    # 1. CLUSTER STRUCTURAL COLUMNS
    # -------------------------------------------------
    struct_words = [w for w in words if is_structural_word(w)]
    xs = sorted(w["x0"] for w in struct_words)

    columns = []

    for x in xs:
        for i, cx in enumerate(columns):
            if abs(cx - x) < (X_TOL * 2):
                columns[i] = (cx + x) / 2
                break
        else:
            columns.append(x)

    columns = sorted(columns)
    columns = columns[:4]  # hard limit

    # -------------------------------------------------
    # 2. DETECT PART NUMBER COLUMN (existing logic)
    # -------------------------------------------------
    col_part_hits = {i: 0 for i in range(len(columns))}

    for w in struct_words:
        for i, cx in enumerate(columns):
            if abs(w["x0"] - cx) < (X_TOL * 2):
                if PART_NO_REGEX.search(w["text"]):
                    col_part_hits[i] += 1

    part_col = max(col_part_hits, key=col_part_hits.get) if col_part_hits else None

    # -------------------------------------------------
    # 3. GROUP WORDS INTO ROWS
    # -------------------------------------------------
    rows = []

    # First sort by vertical position
    for w in sorted(words, key=lambda x: x["top"]):

        placed = False

        for row in rows:
            if abs(row["top"] - w["top"]) < Y_TOL:
                row["words"].append(w)
                placed = True
                break

        if not placed:
            rows.append({
                "top": w["top"],
                "words": [w]
            })

    # -------------------------------------------------
    # ⭐ CRITICAL FIX — ENFORCE LEFT → RIGHT ORDER
    # -------------------------------------------------
    # -------------------------------------------------
    # ⭐ MERGE FRAGMENTED WORDS (HEADER ROWS ONLY)
    # -------------------------------------------------
    
    for i, row in enumerate(rows):
    
        sorted_words = sorted(row["words"], key=lambda w: w["x0"])
    
        # Only apply merge to first 3 rows (headers region)
        if i <= 2:
            row["words"] = _merge_fragmented_words(sorted_words)
        else:
            row["words"] = sorted_words

    # Optional: also sort rows top-to-bottom strictly
    rows = sorted(rows, key=lambda r: r["top"])

    # -------------------------------------------------
    # 4. DETECT TABLE TITLE (NEW)
    # -------------------------------------------------
    table_top_y = min(w["top"] for r in rows for w in r["words"])
    table_title = detect_table_title(words, table_top_y)

    # -------------------------------------------------
    # 5. DEBUG
    # -------------------------------------------------
    if debug:
        print(
            f"[STEP3] Page {page} | "
            f"Columns={len(columns)} | "
            f"Rows={len(rows)} | "
            f"PartCol={part_col}"
        )

        if table_title:
            print(f"[STEP3] Page {page} | Title: {table_title}")

        for i, r in enumerate(rows[:15]):
            print(f"   Row {i+1}: {[w['text'] for w in r['words']]}")

    # -------------------------------------------------
    # 6. RETURN
    # -------------------------------------------------
    return {
        "page": page,
        "columns": columns,
        "rows": rows,
        "part_col": part_col,
        "table_title": table_title,
    }

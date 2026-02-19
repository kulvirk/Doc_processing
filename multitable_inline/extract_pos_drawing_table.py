import re
from multitable_inline.patterns import PART_NO_REGEX

POS_DRAW_PN_REGEX = re.compile(r"\b(?:[A-Z]{1,3}\d{5,}|\d{5,})\b")

def extract_pos_drawing_table(normalized_table, debug=False):

    results = []

    page = normalized_table["page"]
    rows = normalized_table.get("rows", [])

    if not rows:
        return results

    # -------------------------------------------------
    # 1️⃣ FIND HEADER ROW
    # -------------------------------------------------
    header_row = None

    for row in rows[:15]:
        text = " ".join(w["text"].lower() for w in row["words"])

        if (
            "pos" in text
            and "drawing" in text
            and "quantity" in text
            and "item" in text
            and "no" in text
        ):
            header_row = row
            break

    if not header_row:
        return results

    if debug:
        print("\n[POS-DRAW HEADER]")
        print([w["text"] for w in header_row["words"]])

    # -------------------------------------------------
    # 2️⃣ GET HEADER COLUMN ANCHORS
    # -------------------------------------------------
    item_name_x = None
    item_no_x = None
    supplier_x = None

    for i, w in enumerate(header_row["words"]):
        text = w["text"].lower()

        if text == "item":

            if i + 1 < len(header_row["words"]):
                next_text = header_row["words"][i + 1]["text"].lower()
                if "name" in next_text:
                    item_name_x = w["x0"]

            if i + 1 < len(header_row["words"]):
                next_text = header_row["words"][i + 1]["text"].lower().replace(".", "")
                if next_text == "no":
                    item_no_x = w["x0"]

        if text.startswith("supplier"):
            supplier_x = w["x0"]

    if not item_name_x or not item_no_x:
        return results

    page_right = max(
        w["x1"]
        for r in rows
        for w in r["words"]
    )

    # -------------------------------------------------
    # 3️⃣ DEFINE BOUNDS
    # -------------------------------------------------
    DESC_LEFT = item_name_x - 5
    DESC_RIGHT = item_no_x - 20

    PN_LEFT = item_no_x - 5
    PN_RIGHT = supplier_x - 5 if supplier_x else page_right

    if debug:
        print("=" * 80)
        print(f"[POS-DRAW BOUNDS] Page {page}")
        print(f"DESC: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print(f"PN:   {PN_LEFT:.2f} → {PN_RIGHT:.2f}")
        print("=" * 80)

    header_bottom = max(w["bottom"] for w in header_row["words"])

    # -------------------------------------------------
    # 4️⃣ EXTRACT DRAWING NUMBER STRUCTURALLY
    # -------------------------------------------------
    drawing_number = None
    drawing_box = None
    
    for row in rows[:8]:
    
        words = row["words"]
    
        for i, w in enumerate(words):
            raw_text = w["text"]
            text = raw_text.lower().replace(".", "")
    
            if text.startswith("drawnumber"):
    
                # Case 1: merged format like "Drawnumber...:D1160-A1035"
                if ":" in raw_text:
                    value = raw_text.split(":")[-1].strip()
    
                    if value:
                        drawing_number = value
    
                        # Estimate tighter box for value only
                        proportion = len(value) / len(raw_text)
                        value_width = (w["x1"] - w["x0"]) * proportion
    
                        drawing_box = {
                            "text": value,
                            "x0": w["x1"] - value_width,
                            "x1": w["x1"],
                            "top": w["top"],
                            "bottom": w["bottom"],
                        }
                        break
    
                # Case 2: value is next token
                if i + 1 < len(words):
                    next_word = words[i + 1]
                    drawing_number = next_word["text"].strip()
    
                    drawing_box = {
                        "text": next_word["text"],
                        "x0": next_word["x0"],
                        "x1": next_word["x1"],
                        "top": next_word["top"],
                        "bottom": next_word["bottom"],
                    }
                    break
    
        if drawing_number:
            break
            
    # -------------------------------------------------
    # 5️⃣ EXTRACT ROWS
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
            if PN_LEFT <= w["x0"] <= PN_RIGHT
            and POS_DRAW_PN_REGEX.search(w["text"])
        ]

        desc_words = [
            w for w in words
            if DESC_LEFT <= w["x0"] <= DESC_RIGHT
        ]

        # NEW PART ROW
        if pn_words:

            # Emit previous row
            if current_part and current_desc_words:

                description = " ".join(
                    w["text"]
                    for w in sorted(current_desc_words, key=lambda x: (x["top"], x["x0"]))
                ).strip()

                entry = {
                    "page": page,
                    "part_no": current_part,
                    "description": description,
                    "drawing_number": drawing_number or ""
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
                        ]
                    }

                    if drawing_box:
                        entry["trace"]["drawing_box"] = drawing_box

                results.append(entry)

            current_part = " ".join(
                w["text"]
                for w in sorted(pn_words, key=lambda x: x["x0"])
            ).strip()

            current_desc_words = desc_words.copy()
            current_pn_words = pn_words.copy()

        elif desc_words and current_part:
            current_desc_words.extend(desc_words)

    # Emit last row
    if current_part and current_desc_words:

        description = " ".join(
            w["text"]
            for w in sorted(current_desc_words, key=lambda x: (x["top"], x["x0"]))
        ).strip()

        entry = {
            "page": page,
            "part_no": current_part,
            "description": description,
            "drawing_number": drawing_number or ""
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
                ]
            }

            if drawing_box:
                entry["trace"]["drawing_box"] = drawing_box

        results.append(entry)

    if debug:
        print(f"[POS-DRAW] Extracted {len(results)} rows")

    return results

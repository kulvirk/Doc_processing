import re

# Disc column should only emit real numeric PNs (no H14, H03 etc.)
DISC_PN_REGEX = re.compile(r"^\d{5,}$")
MATERIAL_PN_REGEX = re.compile(r"^[A-Z0-9]{4,}$")

def extract_component_list_table(normalized_table, debug=False):
    """
    SPECIAL HANDLER FOR:

    Level | Material | Disc. | BOM item | Description | Remarks

    Extract:
        - Material column as part_no
        - Disc column numeric values as additional part_no
        - Description column as description

    Handles:
        - Wrapped material rows
        - Wrapped description rows
        - Hierarchy markers (.1, ..2, ...3)
    """

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
        texts = {w["text"] for w in row["words"]}

        if {
            "Level",
            "Material",
            "Disc.",
            "BOM",
            "item",
            "Description",
            "Remarks"
        }.issubset(texts):
            header_row = row
            break

    if not header_row:
        return results

    if debug:
        print("\n[COMPONENT LIST HEADER]")
        print([w["text"] for w in header_row["words"]])

    # -------------------------------------------------
    # 2️⃣ GET HEADER X POSITIONS
    # -------------------------------------------------
    page_right = max(
        w["x1"]
        for r in rows
        for w in r["words"]
    )

    material_x = None
    disc_x = None
    desc_x = None

    for w in header_row["words"]:
        if w["text"] == "Material":
            material_x = w["x0"]
        if w["text"] == "Disc.":
            disc_x = w["x0"]
        if w["text"] == "Description":
            desc_x = w["x0"]

    if material_x is None or disc_x is None or desc_x is None:
        return results

    # -------------------------------------------------
    # 3️⃣ DEFINE COLUMN BOUNDS
    # -------------------------------------------------
    MARGIN = 8

    MATERIAL_LEFT = material_x - MARGIN
    MATERIAL_RIGHT = disc_x - MARGIN

    DISC_LEFT = disc_x - MARGIN
    DISC_RIGHT = desc_x - MARGIN

    DESC_LEFT = desc_x - MARGIN
    DESC_RIGHT = page_right

    header_bottom = max(w["bottom"] for w in header_row["words"])

    if debug:
        print("=" * 80)
        print(f"[COMPONENT BOUNDS] Page {page}")
        print(f"MATERIAL: {MATERIAL_LEFT:.2f} → {MATERIAL_RIGHT:.2f}")
        print(f"DISC: {DISC_LEFT:.2f} → {DISC_RIGHT:.2f}")
        print(f"DESC: {DESC_LEFT:.2f} → {DESC_RIGHT:.2f}")
        print("=" * 80)

    # -------------------------------------------------
    # 4️⃣ STATE VARIABLES
    # -------------------------------------------------
    current_material_words = []
    current_disc_words = []
    current_desc_words = []

    # -------------------------------------------------
    # 5️⃣ EMIT FUNCTION
    # -------------------------------------------------

    def emit_current():
        nonlocal current_material_words, current_disc_words, current_desc_words
    
        if not current_material_words:
            return
    
        material_no = "".join(
            w["text"]
            for w in sorted(current_material_words, key=lambda x: (x["top"], x["x0"]))
        ).strip()
    
        description = " ".join(
            w["text"]
            for w in sorted(current_desc_words, key=lambda x: (x["top"], x["x0"]))
        ).strip()
    
        if not material_no or not description:
            return
    
        # ---- Emit MATERIAL ----
        results.append({
            "page": page,
            "part_no": material_no,
            "description": description,
            "trace": {
                "pn_boxes": [
                    {
                        "text": w["text"],
                        "x0": w["x0"],
                        "x1": w["x1"],
                        "top": w["top"],
                        "bottom": w["bottom"],
                    }
                    for w in current_material_words
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
        })
    
        # ---- Emit DISC (if valid numeric PN) ----
        disc_no = "".join(
            w["text"]
            for w in sorted(current_disc_words, key=lambda x: (x["top"], x["x0"]))
        ).strip()
    
        if DISC_PN_REGEX.fullmatch(disc_no):
    
            results.append({
                "page": page,
                "part_no": disc_no,
                "description": description,
                "trace": {
                    "pn_boxes": [
                        {
                            "text": w["text"],
                            "x0": w["x0"],
                            "x1": w["x1"],
                            "top": w["top"],
                            "bottom": w["bottom"],
                        }
                        for w in current_disc_words
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
            })
    
        # Reset
        current_material_words = []
        current_disc_words = []
        current_desc_words = []

    # -------------------------------------------------
    # 6️⃣ PROCESS ROWS
    # -------------------------------------------------
    for row in rows:

        if row["top"] <= header_bottom:
            continue

        words = row["words"]

        row_text = " ".join(w["text"] for w in words).strip()
        # Stop at footer
        if row_text.lower().startswith("printed"):
            break


        # Skip pure hierarchy rows like ".2", "..3"
        if re.fullmatch(r"\.*\d+", row_text):
            continue

        material_words = [
            w for w in words
            if (
                MATERIAL_LEFT <= w["x0"] <= MATERIAL_RIGHT
                and MATERIAL_PN_REGEX.fullmatch(w["text"])
            )
        ]

        disc_words = [
            w for w in words
            if DISC_LEFT <= w["x0"] <= DISC_RIGHT
        ]

        desc_words = [
            w for w in words
            if DESC_LEFT <= w["x0"] <= DESC_RIGHT
        ]

        # -------------------------------------------------
        # NEW MATERIAL ROW
        # -------------------------------------------------
        if material_words:
            if current_material_words:
                emit_current()

            current_material_words.extend(material_words)
            current_disc_words.extend(disc_words)
            current_desc_words.extend(desc_words)

        # -------------------------------------------------
        # CONTINUATION ROW
        # -------------------------------------------------
        elif current_material_words:
            # If disc continues on next line
            if disc_words:
                current_disc_words.extend(disc_words)

            if desc_words:
                current_desc_words.extend(desc_words)

    # Emit final row
    if current_material_words:
        emit_current()

    if debug:
        print(f"\n[COMPONENT LIST] Extracted {len(results)} rows")

    return results

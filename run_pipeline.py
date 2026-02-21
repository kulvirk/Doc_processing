from collections import defaultdict, Counter
from openpyxl import Workbook
import os,re
from multitable_inline.extract_mark_table import extract_mark_table
from multitable_inline.extract_pmh_mos_table import extract_pmh_mos_table
from multitable_inline.extract_balloon_bom_table import extract_balloon_bom_table
from multitable_inline.extract_recommended_spares_table import extract_recommended_spares_table
from multitable_inline.extract_split_header_item_part_table import extract_split_header_item_part_table
from multitable_inline.extract_single_level_bom import extract_single_level_bom
from multitable_inline.extract_article_number_table import extract_article_number_table
from multitable_inline.extract_pos_drawing_table import extract_pos_drawing_table
from multitable_inline.extract_pos_item_table import extract_pos_item_table
from multitable_inline.simple_2col_table import extract_simple_2col_table
from multitable_inline.extract_component_list import extract_component_list_table
from multitable_inline.simple_3col_table import extract_simple_3col_table
from multitable_inline.step1_extract_tables import extract_table_candidates
from multitable_inline.step2_select_tables import is_parts_table
from multitable_inline.step3_geometry_normalize import normalize_table
from multitable_inline.step4_extract_parts import extract_parts
from multitable_inline.inline_pn_extractor import extract_inline_pns
from multitable_inline.extract_alt_id_parts import extract_alt_id_parts
from multitable_inline.patterns import PART_NO_REGEX
from multitable_inline.title_extractor import (extract_page_title, extract_prev_page_title)

KNOWN_VENDORS = [
    "INGERSOLL RAND",
    "Marlow Pumps",
    "DECKMA HAMBURG GmbH",
    "Cameron",
    "NEUHAUS",
    "Expro",
    "HANNON HYDRAULICS",
    "WILO",
    "VETCOGRAY",
    "GE OIL & GAS",
    "Dropsafe",
    "PHAROS MARINE AUTOMATIC POWER",
    "NOV",
    "Survival Systems",
    "BIRDDONG ASSOCIATES INC",
    "Letourneau",
    "FEDERAL SIGNAL",
    "EMERSON",
    "QUINCY",
    "RAM WINCH HOIST",
    "GE Oil and Gas",
    "Bauer Kompressoren",
    "Eaton",
    "SOUTHERN AVIONICS COMPANY",
    "LOADMASTER INDUSTRIES Broussard",
    "NATIONAL OILWELL VARCO",
    "LOADMASTER DERRICK",
    "JOHNSON",
    "ALSTOM",
    "Conver team",
    "IEC System",
    "cameron",
    "GENERAL MONITORS",
    "peerless Pump",
    "KIDDE FIRE SYSTEM",
    "Dooley Tackaberry Systems",
    "ALFA LAVAL TUMBA AB",
    "Roper Pump Company",
    "Dooley Tackaberry",
    "ANSUL",
    "LEWCO",
    "DOUBLE LIFE",
    "LTI TECHNOLOGIES",
    "TOTCO",
    "HARWIL",
    "T3 ENERGY SERVICES",
    "IMECO",
    "NANCE INTERNATIONAL, INC.",
    "CARRIER",
    "EPIC",
    "AXIOM",
    "Derrick",
    "CATERPILLAR.INC",
    "RECOVERED ENERGY .INC",
    "Federal Signal Corporation",
    "AQUAFINEUV",
    "SPECIFIC EQUIPMENT COMPANY1",
    "Hadar Lighting",
    "MURPHY",
    "KODEN",
    "JORTON",
    "ALSTOM",
    "Totco",
    "DOOLEYTAKEBERRY Inc",
    "ALFA LAVAL",
    "BESLER ELECTRIC",
    "PepperL",
    "Signal International",
    "Vertical",
    "WILKERSON"
]

def detect_vendor_from_filename(pdf_path, pages_data, known_vendors):
    """
    Extract vendor + model from filename,
    but only accept if vendor or model appears in first page text.
    """

    if not pages_data:
        return None, None

    # -----------------------------
    # First page text
    # -----------------------------
    first_page_text = pages_data[0].get("page_text", "").upper()

    # -----------------------------
    # Extract filename
    # -----------------------------
    filename = os.path.basename(pdf_path)
    name = os.path.splitext(filename)[0]

    # Normalize
    clean_name = re.sub(r"[_\-]+", " ", name).upper().strip()
    parts = clean_name.split()

    if not parts:
        return None, None

    # -----------------------------
    # Try matching known vendor
    # -----------------------------
    vendor = None
    model = None

    for v in known_vendors:
        if v in clean_name:
            vendor = v
            break

    # Model = everything except vendor
    if vendor:
        model_candidate = clean_name.replace(vendor, "").strip()
        model = model_candidate if model_candidate else None
    else:
        return None, None

    # -----------------------------
    # VALIDATION STEP
    # -----------------------------
    # Accept only if vendor or model appears in first page
    if vendor in first_page_text:
        return vendor, model

    if model and model in first_page_text:
        return vendor, model

    # Not validated
    return None, None

def detect_vendor_from_text(pages_data, known_vendors):

    if not pages_data:
        return None

    first_page_text = pages_data[0].get("page_text", "").upper()

    for vendor in known_vendors:
        if vendor in first_page_text:
            return vendor

    return None

def detect_model_from_text(pages_data):

    if not pages_data:
        return None

    text = pages_data[0].get("page_text", "")
    if not text:
        return None

    keywords = [
        "MODEL",
        "SERIES",
        "PROJECT",
        "TYPE",
        "CODE",
        "P/N",
        "PN",
        "PART NO",
        "MODEL NO"
    ]

    lines = text.splitlines()

    for line in lines:
        line_upper = line.strip().upper()

        for kw in keywords:
            if line_upper.startswith(kw):

                # Remove keyword + optional ":" or "-"
                value = re.sub(
                    rf"^{kw}\s*[:\-]?\s*",
                    "",
                    line.strip(),
                    flags=re.IGNORECASE
                )

                if value:
                    return value.strip()

    return None

def detect_vendor(pdf_path, pages_data, known_vendors):

    # 1️⃣ Try filename first
    vendor, model = detect_vendor_from_filename(
    pdf_path,
    pages_data,
    KNOWN_VENDORS
)

    if not vendor:
        vendor = detect_vendor_from_text(pages_data, known_vendors)
    if not model:
        model=detect_model_from_text(pages_data)

    return vendor,model
def _first_pn_top(words, debug=False):

    tops = []

    for w in words:
        if PART_NO_REGEX.search(w.get("text", "")):
            tops.append(w["top"])
            if debug:
                print(f"[PN-CANDIDATE] text={w['text']} top={w['top']}")

    if not tops:
        if debug:
            print("[PN-TOP] None found")
        return None

    first_top = min(tops)

    if debug:
        print(f"[PN-TOP] Selected anchor top={first_top}")

    return first_top
# ==================================================
# EXPORT WITH SUMMARY (UNCHANGED)
# ==================================================
def export_with_summary(all_parts,
    pages_data,
    output_xlsx,
    vendor=None,
    model=None,
    project=None,
    subproject=None,
    equipment=None,
    pdf_path=None):
    
    wb = Workbook()
    vendor = vendor or "N/A"
    model = model or "N/A"
    project = project or "N/A"
    subproject = subproject or "N/A"
    equipment = equipment or "N/A"

    filename = "N/A"
    if pdf_path:
        import os
        filename = os.path.basename(pdf_path)

    # -------------------------------
    # SHEET 1: PARTS
    # -------------------------------
    ws_parts = wb.active
    ws_parts.title = "Parts"

    ws_parts.append([
        "Vendor",
        "Model",
        "DESCRIPTION",
        "Title_EQUIPMENT_PROJECT",
        "Drawing",
        "No Item-(Mnl)",
        "pageno_FILENAME",
        "project",
        "Sub Project No-(Mnl)",
        "Equipment Name-(Mnl)"
    ])
    for p in all_parts:
        ws_parts.append([
            vendor,
            model,
            p["description"],
            p.get("title", ""),
            p.get("drawing_number", ""),
            p["part_no"],
            f'{p["page"]}_{filename}',
            project,
            subproject,
            equipment
        ])

    # -------------------------------
    # SHEET 2: SUMMARY
    # -------------------------------
    ws_summary = wb.create_sheet("Summary")

    pages_scanned = len(pages_data)
    total_parts = len(all_parts)

    parts_per_page = defaultdict(int)
    pn_counts = Counter()
    pn_pages = defaultdict(set)

    for p in all_parts:
        parts_per_page[p["page"]] += 1
        pn_counts[p["part_no"]] += 1
        pn_pages[p["part_no"]].add(p["page"])

    duplicate_pns = {
        pn: {
            "count": cnt,
            "pages": sorted(pn_pages[pn])
        }
        for pn, cnt in pn_counts.items()
        if cnt > 1
    }

    ws_summary.append(["Metric", "Value"])
    ws_summary.append(["Pages scanned", pages_scanned])
    ws_summary.append(["Total parts extracted", total_parts])
    ws_summary.append(["Pages with parts", len(parts_per_page)])
    ws_summary.append(["Pages without parts", pages_scanned - len(parts_per_page)])
    ws_summary.append(["Duplicate part numbers", len(duplicate_pns)])

    ws_summary.append([])
    ws_summary.append(["Parts per page"])
    ws_summary.append(["Page", "Count"])

    for page in sorted(parts_per_page):
        ws_summary.append([page, parts_per_page[page]])

    ws_summary.append([])
    ws_summary.append(["Duplicate Part Numbers"])
    ws_summary.append(["Part No", "Occurrences", "Pages"])

    for pn, info in duplicate_pns.items():
        ws_summary.append([
            pn,
            info["count"],
            ", ".join(map(str, info["pages"]))
        ])

    wb.save(output_xlsx)
    return output_xlsx


# ==================================================
# MAIN PIPELINE (FIXED, BACKWARD-COMPATIBLE)
# ==================================================
def run(
    pdf_path,
    output_csv,
    vendor=None,
    model=None,
    project=None,
    subproject=None,
    equipment=None,
    debug=False,
    pages=None
):
    all_parts = []

    # ----------------------------------------------
    # STEP 1 — Extract words from ALL pages
    # ----------------------------------------------
    pages_data = extract_table_candidates(pdf_path)
    if not vendor:
        vendor, b= detect_vendor(pdf_path, pages_data, KNOWN_VENDORS)
    if not model:
        a,model = detect_vendor(pdf_path, pages_data, KNOWN_VENDORS)


    if debug:
        print(f"[PIPELINE] Total pages scanned: {len(pages_data)}")

    # ----------------------------------------------
    # MAIN LOOP
    # ----------------------------------------------
    for i, page_data in enumerate(pages_data):
    
        page_no = page_data["page"]
    
        if pages and page_no not in pages:
            continue
    
        words = page_data.get("words", [])
        page_text_lower = page_data.get("page_text", "").lower()
    
        extracted_parts = []
        normalized = None
    
        import re
    
        # =====================================================
        # ⭐ 1️⃣ FORCE MARK TABLE (HIGHEST PRIORITY)
        # =====================================================
        if (
            re.search(r"\bmark\b", page_text_lower)
            and re.search(r"\bdwg\b", page_text_lower)
            and re.search(r"\bdescription\b", page_text_lower)
        ):
            if debug:
                print(f"[PIPELINE] Page {page_no} | FORCED MARK TABLE MODE")
    
            normalized = normalize_table(page_data, debug=debug)
    
            if normalized and normalized.get("rows"):
                extracted_parts = extract_mark_table(
                    normalized,
                    debug=debug
                )
    
        # =====================================================
        # ⭐ 2️⃣ POS-ITEM TABLE (BEFORE STEP2)
        # =====================================================
        elif any(
            (
                "pos" in row_text
                and "qty" in row_text
                and "item name" in row_text
                and "item no" in row_text
                and "drawing reference" in row_text
            )
            for row_text in [
                " ".join(w["text"].lower() for w in row["words"])
                for row in normalize_table(page_data)["rows"][:15]
            ]
        ):
            if debug:
                print(f"[PIPELINE] Page {page_no} | POS-ITEM TABLE MODE")
    
            normalized = normalize_table(page_data, debug=debug)
    
            if normalized and normalized.get("rows"):
                extracted_parts = extract_pos_item_table(
                    normalized,
                    debug=debug
                )
    
        # =====================================================
        # ⭐ 3️⃣ SIMPLE 3-COLUMN TABLE (INDEPENDENT)
        # =====================================================
        elif (
            "qty" in page_text_lower
            and "part number" in page_text_lower
            and "description" in page_text_lower
        ):
            if debug:
                print(f"[PIPELINE] Page {page_no} | TRY SIMPLE 3COL MODE")
    
            normalized = normalize_table(page_data, debug=debug)
    
            if normalized and normalized.get("rows"):
                simple_parts = extract_simple_3col_table(
                    normalized,
                    debug=debug
                )
    
                if simple_parts:
                    extracted_parts = simple_parts
    
        # =====================================================
        # ⭐ 4️⃣ GENERIC TABLE HANDLING (STEP2)
        # =====================================================
        else:
    
            table_type = is_parts_table(page_data, debug=debug)
    
            if table_type:
    
                normalized = normalize_table(page_data, debug=debug)
    
                # ---------- COMPONENT LIST ----------
                if (
                    normalized
                    and any(
                        {
                            "Level",
                            "Material",
                            "Disc.",
                            "BOM",
                            "item",
                            "Description",
                            "Remarks"
                        }.issubset({w["text"] for w in row["words"]})
                        for row in normalized["rows"][:12]
                    )
                ):
                    if debug:
                        print(f"[PIPELINE] Page {page_no} | COMPONENT LIST MODE")
    
                    extracted_parts = extract_component_list_table(
                        normalized,
                        debug=debug
                    )
    
                # ---------- ALT-ID TABLE ----------
                elif table_type == "ALT_ID_TABLE":
    
                    if normalized and normalized.get("rows"):
                        extracted_parts = extract_alt_id_parts(
                            normalized,
                            debug=debug
                        )
    
                # ---------- SIMPLE 2COL ----------
                elif table_type == "SIMPLE_2COL_TABLE":
    
                    if normalized and normalized.get("rows"):
                        extracted_parts = extract_simple_2col_table(
                            normalized,
                            debug=debug
                        )
                        
                # ---------- POS DRAWING TABLE ----------
                elif any(
                    "item name/technical" in " ".join(w["text"].lower() for w in row["words"])
                    for row in normalized["rows"][:12]
                ):
                    if debug:
                        print(f"[PIPELINE] Page {page_no} | POS-DRAW TABLE MODE")
                
                    extracted_parts = extract_pos_drawing_table(
                        normalized,
                        debug=debug
                    )

                # ---------- ARTICLE NUMBER TABLE ----------
                elif any(
                    (
                        "article" in row_text
                        and "number" in row_text
                        and "description" in row_text
                        and "certificate" in row_text
                    )
                    for row_text in [
                        " ".join(w["text"].lower().replace(".", "") for w in row["words"])
                        for row in normalized["rows"][:15]
                    ]
                ):
                    if debug:
                        print(f"[PIPELINE] Page {page_no} | ARTICLE-NUMBER TABLE MODE")
                
                    extracted_parts = extract_article_number_table(
                        normalized,
                        debug=debug
                    )
                # ⭐ SINGLE LEVEL BOM MODE
                # ⭐ SINGLE LEVEL BOM MODE
                elif any(
                    {"no.", "item", "rev", "description"}.issubset(
                        {w["text"].lower().strip() for w in row["words"]}
                    )
                    for row in normalize_table(page_data)["rows"][:12]
                ):
                    if debug:
                        print(f"[PIPELINE] Page {page_no} | SINGLE LEVEL BOM MODE")
                
                    normalized = normalize_table(page_data, debug=debug)
                
                    if normalized and normalized.get("rows"):
                        extracted_parts = extract_single_level_bom(
                            normalized,
                            debug=debug
                        )
                
                # ⭐ SPLIT HEADER ITEM/PART TABLE
                elif (
                    lambda normalized: any(
                        (
                            {"item", "part"}.issubset(
                                {w["text"].lower() for w in normalized["rows"][i]["words"]}
                            )
                            and
                            "number" in {w["text"].lower() for w in normalized["rows"][i + 1]["words"]}
                            and
                            "qty." in {w["text"].lower() for w in normalized["rows"][i + 1]["words"]}
                            and
                            "description" in {w["text"].lower() for w in normalized["rows"][i + 1]["words"]}
                        )
                        for i in range(len(normalized["rows"]) - 1)
                    )
                )(
                    normalize_table(page_data)
                ):
                    if debug:
                        print(f"[PIPELINE] Page {page_no} | SPLIT HEADER TABLE MODE")
                
                    normalized = normalize_table(page_data, debug=debug)
                
                    extracted_parts = extract_split_header_item_part_table(
                        normalized,
                        debug=debug
                    )

                # ---------- BALLOON BOM TABLE ----------
                elif any(
                    (
                        "balloon" in row1_text
                        and "part" in row1_text
                        and "number" in row2_text
                        and "rev" in row2_text
                        and "description" in row2_text
                    )
                    for row1_text, row2_text in [
                        (
                            " ".join(w["text"].lower() for w in normalized["rows"][i]["words"]),
                            " ".join(w["text"].lower() for w in normalized["rows"][i + 1]["words"])
                        )
                        for i in range(len(normalized["rows"]) - 1)
                    ]
                ):
                    if debug:
                        print(f"[PIPELINE] Page {page_no} | BALLOON BOM TABLE MODE")
                
                    extracted_parts = extract_balloon_bom_table(
                        normalized,
                        debug=debug
                    )

                elif any(
                    [
                        [w["text"] for w in row["words"]] ==
                        ['Parts', 'List', 'Item', 'Qty', 'Description', 'PMH', 'Part', 'No']
                        for row in normalized["rows"][:12]
                    ]
                ):
                    if debug:
                        print(f"[PIPELINE] Page {page_no} | RECOMMENDED SPARES MODE")
                
                    extracted_parts = extract_recommended_spares_table(
                        normalized,
                        debug=debug
                    )

                # ⭐ PMH / MOS TABLE MODE
                elif any(
                    (
                        "item" in row_text
                        and "qty" in row_text
                        and "description" in row_text
                        and ("pmh part no" in row_text or "mos part no" in row_text)
                    )
                    for row_text in [
                        " ".join(w["text"].lower() for w in row["words"])
                        for row in normalize_table(page_data)["rows"][:8]
                    ]
                ):
                    if debug:
                        print(f"[PIPELINE] Page {page_no} | PMH/MOS TABLE MODE")
                
                    normalized = normalize_table(page_data, debug=debug)
                
                    extracted_parts = extract_pmh_mos_table(
                        normalized,
                        debug=debug
                    )


                # ---------- NORMAL TABLE ----------
                else:
    
                    if normalized and normalized.get("rows"):
                        extracted_parts = extract_parts(
                            normalized,
                            debug=debug
                        )
    
            # -------------------------------------------------
            # INLINE EXTRACTION (ONLY IF NOT TABLE)
            # -------------------------------------------------
            else:
                extracted_parts = extract_inline_pns(
                    page_data,
                    debug=debug
                )

        # =====================================================
        # TITLE EXTRACTION (UPDATED PRIORITY)
        # =====================================================
        # =====================================================
        # TITLE EXTRACTION (WITH DEBUG TRACE SUPPORT)
        # =====================================================
        
        if not extracted_parts:
            continue
        
        title = None
        title_words = []
        
        # 1️⃣ Prefer table structural title
        if extracted_parts and extracted_parts[0].get("title"):
            title = extracted_parts[0]["title"]
        
            # structural titles already carry title_boxes via extractor
            # so we don't need to re-detect words here
        
        # 2️⃣ Page-level title detection
        if not title:
            # --------------------------------------------------
            # ANCHOR: derive from extracted parts (preferred)
            # --------------------------------------------------
            
            pn_top = None
            
            if extracted_parts:
                for p in extracted_parts:
                    trace = p.get("trace")
                    if trace and trace.get("pn_boxes"):
                        pn_top = min(box["top"] for box in trace["pn_boxes"])
                        if debug:
                            print(f"[PN-ANCHOR-FROM-TRACE] top={pn_top}")
                        break
            
            # Fallback only if no trace anchor found
            if pn_top is None:
                pn_top = _first_pn_top(words, debug=debug)
            
            # Now run page title detection
            if pn_top is not None:
                result = extract_page_title(words, pn_top)

                if result:
                    title, title_words = result
        
                    # Capture actual words that form this title
                    title_words = [
                        w for w in words
                        if w["text"] in title.split()
                        and w["top"] < pn_top
                    ]
        
        # 3️⃣ Previous-page fallback
        if not title and i > 0:
            prev_words = pages_data[i - 1].get("words", [])
            detected_title = extract_prev_page_title(prev_words)
        
            if detected_title:
                title = detected_title
        
        # Apply title to all parts
        for p in extracted_parts:
            p["title"] = title or ""
        
            # 🔴 Inject title boxes into trace for overlay
            if debug and title_words:
                if "trace" not in p:
                    p["trace"] = {}
        
                p["trace"]["title_boxes"] = [
                    {
                        "text": w["text"],
                        "x0": w["x0"],
                        "x1": w["x1"],
                        "top": w["top"],
                        "bottom": w["bottom"],
                    }
                    for w in title_words
                ]
        
        if debug:
            print(
                f"[TITLE] Page {page_no} | "
                f"{title if title else 'NONE'}"
            )

        all_parts.extend(extracted_parts)
    
    # =====================================================
    # FINAL DEBUG
    # =====================================================
    if debug:
        print(f"[PIPELINE] Total parts extracted: {len(all_parts)}")


    # ----------------------------------------------
    # EXPORT XLSX (UNCHANGED)
    # ----------------------------------------------
    output_xlsx = output_csv.replace(".csv", ".xlsx")

    export_with_summary(
    all_parts=all_parts,
    pages_data=pages_data,
    output_xlsx=output_xlsx,
    vendor=vendor,
    model=model,
    project=project,
    subproject=subproject,
    equipment=equipment,
    pdf_path=pdf_path
)

    # ----------------------------------------------
    # DEBUG OVERLAY PDF (UNCHANGED)
    # ----------------------------------------------
    if debug:
        from multitable_inline.debug_overlay import generate_debug_pdf
        import os

        base, ext = os.path.splitext(pdf_path)
        debug_pdf = base + "_debug.pdf"

        generate_debug_pdf(
            original_pdf=pdf_path,
            output_pdf=debug_pdf,
            extracted_parts=all_parts
        )

        print(f"[DEBUG] Overlay PDF written to {debug_pdf}")

    return output_xlsx


# ==================================================
# CLI
# ==================================================
if __name__ == "__main__":
   run(
    pdf_path=r"Quicy QR-370LS.pdf",
    output_csv=r"QR-370LS.csv",


    
    debug=True
)
 





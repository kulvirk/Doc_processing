from collections import defaultdict, Counter
from openpyxl import Workbook
from PyPDF2 import PdfReader, PdfWriter
import os
import tempfile
from multitable_inline.extract_mark_table import extract_mark_table
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

def _first_pn_top(words):
    """
    Find the vertical position of the first PN on the page.
    Used as anchor to look ABOVE table/paragraph.
    """
    tops = [
        w["top"] for w in words
        if PART_NO_REGEX.search(w.get("text", ""))
    ]
    return min(tops) if tops else None


# ==================================================
# EXPORT WITH SUMMARY (UNCHANGED)
# ==================================================
def export_with_summary(all_parts, pages_data, output_xlsx):
    wb = Workbook()

    # -------------------------------
    # SHEET 1: PARTS
    # -------------------------------
    ws_parts = wb.active
    ws_parts.title = "Parts"

    ws_parts.append(["page", "title", "part_no", "description", "drawing_number"])

    for p in all_parts:
        ws_parts.append([
            p["page"],
            p.get("title", ""),
            p["part_no"],
            p["description"],
            p.get("drawing_number", "")
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
    debug=False,
    pages=None
):
    all_parts = []

    # ----------------------------------------------
    # STEP 1 — Extract words from ALL pages
    # ----------------------------------------------
    pages_data = extract_table_candidates(pdf_path)

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
        # TITLE EXTRACTION
        # =====================================================
        if not extracted_parts:
            continue
    
        pn_top = _first_pn_top(words)
        title = None
    
        if pn_top is not None:
            title = extract_page_title(words, pn_top)
    
        if not title and i > 0:
            prev_words = pages_data[i - 1].get("words", [])
            title = extract_prev_page_title(prev_words)
    
        for p in extracted_parts:
            p["title"] = title or ""
    
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
        output_xlsx=output_xlsx
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
        pdf_path=r"combined.pdf",
        output_csv=r"combined.csv",
        debug=True,
        pages=[1,2,3]
    )
 



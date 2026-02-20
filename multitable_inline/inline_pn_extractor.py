import re

PN_REGEX = re.compile(
    r"\(P\/N\s*([0-9A-Z\-\/]+)\)",
    re.IGNORECASE
)

SENTENCE_SPLIT_REGEX = re.compile(r'[.!?]')

MAX_DESC_CHARS = 300
MAX_DESC_SENTENCES = 2


def extract_inline_pns(table_candidate, debug=False):
    page = table_candidate["page"]
    text = table_candidate.get("page_text", "")
    words = table_candidate.get("words", [])

    if not text or "P/N" not in text:
        return []

    # Normalize text
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    full_text = " ".join(lines)

    matches = list(PN_REGEX.finditer(full_text))
    if not matches:
        return []

    results = []
    seen = set()

    for idx, m in enumerate(matches):
        pn = m.group(1)
        key = (page, pn)
        if key in seen:
            continue
        seen.add(key)

        # -----------------------------------------
        # RIGHT boundary = PN start
        # -----------------------------------------
        right = m.start()

        # -----------------------------------------
        # LEFT boundary = nearest sentence boundary
        # -----------------------------------------
        left = 0

        # 1) Look backwards for sentence boundary
        prefix = full_text[:right]
        sent_matches = list(SENTENCE_SPLIT_REGEX.finditer(prefix))
        if sent_matches:
            left = sent_matches[-1].end()

        # 2) If previous PN is closer, prefer it
        if idx > 0:
            prev_end = matches[idx - 1].end()
            if prev_end > left:
                left = prev_end

        desc = full_text[left:right].strip()

        # -----------------------------------------
        # Cleanup
        # -----------------------------------------
        desc = desc.lstrip("0123456789.-• ")

        if ":" in desc:
            desc = desc.split(":", 1)[-1].strip()

        if not desc:
            continue

        # -----------------------------------------
        # Locality bounds
        # -----------------------------------------
        if len(desc) > MAX_DESC_CHARS:
            desc = desc[:MAX_DESC_CHARS].rsplit(" ", 1)[0]

        sentences = re.split(r'(?<=[.!?])\s+', desc)
        if len(sentences) > MAX_DESC_SENTENCES:
            desc = " ".join(sentences[:MAX_DESC_SENTENCES])

        if len(desc) < 4:
            continue

        # ------------------------------
        # Geometry capture
        # ------------------------------

        # ------------------------------
        # Geometry capture (clean version)
        # ------------------------------
        
        pn_boxes = []
        desc_boxes = []
        
        # 1️⃣ Find PN words (substring match)
        for w in words:
            if pn in w["text"]:
                pn_boxes.append({
                    "text": w["text"],
                    "x0": w["x0"],
                    "x1": w["x1"],
                    "top": w["top"],
                    "bottom": w["bottom"],
                })
        
        if pn_boxes:
            pn_word = pn_boxes[0]
            pn_top = pn_word["top"]
            pn_x0 = pn_word["x0"]
        
            # 2️⃣ Capture words on same line, left of PN only
            for w in words:
                if (
                    abs(w["top"] - pn_top) < 8 and
                    w["x1"] <= pn_x0
                ):
                    desc_boxes.append({
                        "text": w["text"],
                        "x0": w["x0"],
                        "x1": w["x1"],
                        "top": w["top"],
                        "bottom": w["bottom"],
                    })

        results.append({
            "page": page,
            "part_no": pn,
            "description": desc,
            "trace": {
                "pn_boxes": pn_boxes,
                "desc_boxes": desc_boxes
            }
        })

        if debug:
            print(f"[INLINE] Page {page} | {pn} | {desc}")

    return results

def _group_lines(words):
    lines = {}
    for w in words:
        key = round(w["top"], 1)
        lines.setdefault(key, []).append(w)
    return lines


def _is_bold(ws):
    for w in ws:
        if "bold" in w.get("fontname", "").lower():
            return True
    return False

def _looks_like_text(text):

    if not text:
        return False

    printable = sum(32 <= ord(c) <= 126 for c in text)
    if printable / len(text) < 0.7:
        return False

    alpha = sum(c.isalpha() for c in text)
    alpha_ratio = alpha / len(text)

    if alpha_ratio < 0.5:
        return False

    # NEW: reject high symbol density
    non_alnum = sum(not c.isalnum() and not c.isspace() for c in text)
    if non_alnum / len(text) > 0.2:
        return False

    return True


def extract_page_title(words, pn_top):
    """
    SAME PAGE:
    - consider ONLY content above PN/table
    - pick highest font line
    - prefer bold if available
    - prefer longer text if tie
    """

    if not words or pn_top is None:
        return None

    lines = _group_lines(words)
    candidates = []

    for top, ws in lines.items():
        
        if top >= pn_top:
            continue

        text = " ".join(w["text"] for w in ws).strip()
        if len(text) < 5 or len(text) > 150:
            continue
        
        # Reject single short words
        if len(text.split()) == 1 and len(text) < 8:
            continue
        if not any(c.isalpha() for c in text):
            continue
        if not _looks_like_text(text):
            continue

        sizes = [w["size"] for w in ws if "size" in w]
        if not sizes:
            continue

        avg_size = sum(sizes) / len(sizes)
        bold = _is_bold(ws)

        candidates.append({
            "top": top,
            "size": avg_size,
            "bold": bold,
            "text": text,
            "words": ws
        })

    if not candidates:
        return None

    # 1) highest font size wins
    
    candidates.sort(key=lambda x: x["size"], reverse=True)
    max_size = candidates[0]["size"]
    
    top_font = [c for c in candidates if c["size"] >= max_size * 0.95]

    # 2) prefer bold
    bold_candidates = [c for c in top_font if c["bold"]]
    final = bold_candidates if bold_candidates else top_font

    # 3) prefer longer text, then closest to table
    final.sort(
        key=lambda x: (
            len(x["text"]),
            x["top"]
        ),
        reverse=True
    )
    selected = final[0]
    return selected["text"], selected["words"]


def extract_prev_page_title(words):
    """
    PREVIOUS PAGE FALLBACK:
    - highest font on page
    - prefer bold
    """

    if not words:
        return None

    lines = _group_lines(words)
    candidates = []

    for top, ws in lines.items():
        text = " ".join(w["text"] for w in ws).strip()

        if len(text) < 3 or len(text) > 150:
            continue
        if not any(c.isalpha() for c in text):
            continue
        if not _looks_like_text(text):
            continue

        sizes = [w["size"] for w in ws if "size" in w]
        if not sizes:
            continue

        avg_size = sum(sizes) / len(sizes)
        bold = _is_bold(ws)

        candidates.append({
            "size": avg_size,
            "bold": bold,
            "text": text
        })

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["size"], reverse=True)
    max_size = candidates[0]["size"]

    top_font = [c for c in candidates if c["size"] >= max_size * 0.95]
    bold_candidates = [c for c in top_font if c["bold"]]

    return (bold_candidates or top_font)[0]["text"]

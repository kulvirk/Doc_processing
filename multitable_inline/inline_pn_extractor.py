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

        results.append({
            "page": page,
            "part_no": pn,
            "description": desc
        })

        if debug:
            print(f"[INLINE] Page {page} | {pn} | {desc}")

    return results

import re

# Numeric-first, industrial-safe part numbers
PART_NO_REGEX = re.compile(
    r"""
    \b
    (
        (?!\d{1,2}-[A-Za-z]{3})          # exclude dates like 24-Oct

        \d{5,9}                         # pure numeric (existing)
        |
        \d{2,6}[-/][0-9A-Z]{2,6}        # hyphen/slash (existing)

        |
        \d{2}[A-Z]{2}\d{3,}             # 01PS0002, 23CN0104
        |
        [A-Z]{3,}\d{3,}[A-Z]?           # OEM2906B
    )
    \b
    """,
    re.VERBOSE
)



# Headers that indicate non-data rows
PART_NUMBER_HEADERS = {
    "part no",
    "partno.",
    "partno",
    "parts",
    "part number",
    "p/n",
    "pn",
    "pin",
    "kit",
    "kit number",
    "kit no",
    "item",
    "component",
    "component item",
    "article no",
    "article number",

    # NEW — industrial manuals often misuse this
    "material",
    "material no",
    "material number",
}


# Geometry tolerances (unchanged)
X_TOL = 15
Y_TOL = 5

import streamlit as st
import tempfile
import os

from run_pipeline import run

st.set_page_config(
    page_title="Parts",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Parts Extractor — PDF → Excel")

# ======================================================
# FILE UPLOAD
# ======================================================

uploaded_file = st.file_uploader(
    "Upload PDF Manual",
    type=["pdf"]
)

# ======================================================
# METADATA INPUT (NEW SECTION)
# ======================================================

st.subheader("Project & Equipment Details (Optional)")

col1, col2 = st.columns(2)

vendor = col1.text_input("Vendor")
model = col2.text_input("Model")

project = col1.text_input("Project")
subproject = col2.text_input("Sub Project")

equipment = st.text_input("Equipment Name")

# Convert empty strings → None
vendor = vendor.strip() or None
model = model.strip() or None
project = project.strip() or None
subproject = subproject.strip() or None
equipment = equipment.strip() or None


# ======================================================
# PAGE SELECTION MODE
# ======================================================

st.subheader("Page Selection")

mode = st.radio(
    "Choose mode",
    ["All pages", "Page range", "Specific pages"]
)

pages = None

# ---------- PAGE RANGE ----------
if mode == "Page range":

    col1, col2 = st.columns(2)

    start_page = col1.number_input(
        "Start Page",
        min_value=1,
        value=1
    )

    end_page = col2.number_input(
        "End Page",
        min_value=1,
        value=1
    )

    if start_page > end_page:
        st.error("Start page must be ≤ End page")
    else:
        pages = list(range(start_page, end_page + 1))

# ---------- SPECIFIC PAGES ----------
elif mode == "Specific pages":

    page_input = st.text_input(
        "Enter pages (comma-separated)",
        placeholder="e.g. 1,3,5,8,10"
    )

    if page_input:
        try:
            pages = sorted({
                int(p.strip())
                for p in page_input.split(",")
                if p.strip()
            })
        except ValueError:
            st.error("Invalid page numbers")

# ======================================================
# OPTIONS
# ======================================================

st.subheader("Options")

debug = st.checkbox(
    "Generate debug overlay PDF",
    value=False
)

# ======================================================
# RUN BUTTON
# ======================================================

if st.button("🚀 Run Extraction", use_container_width=True):

    if not uploaded_file:
        st.error("Please upload a PDF file")
        st.stop()

    # Save uploaded file temporarily
    # with tempfile.NamedTemporaryFile(
    #     delete=False,
    #     suffix=".pdf"
    # ) as tmp:

    #     tmp.write(uploaded_file.read())
    #     pdf_path = tmp.name
    # Create temp directory
    temp_dir = tempfile.gettempdir()
    
    # Use original filename
    original_name = uploaded_file.name
    
    pdf_path = os.path.join(temp_dir, original_name)
    
    with open(pdf_path, "wb") as f:
        f.write(uploaded_file.read())

    output_csv = pdf_path.replace(".pdf", ".csv")

    progress = st.progress(0)
    progress.progress(20)

    with st.spinner("Processing document..."):

        output_xlsx = run(
            pdf_path=pdf_path,
            output_csv=output_csv,
            vendor=vendor,
            model=model,
            project=project,
            subproject=subproject,
            equipment=equipment,
            debug=debug,
            pages=pages
        )

    progress.progress(100)

    st.success("Extraction completed successfully!")

    # ==================================================
    # DOWNLOAD OUTPUT
    # ==================================================

    with open(output_xlsx, "rb") as f:
        st.download_button(
            "⬇️ Download Excel Output",
            f,
            file_name=os.path.basename(output_xlsx),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # Optional debug PDF download
    if debug:
        debug_pdf = pdf_path.replace(".pdf", "_debug.pdf")

        if os.path.exists(debug_pdf):
            with open(debug_pdf, "rb") as f:
                st.download_button(
                    "⬇️ Download Debug Overlay PDF",
                    f,
                    file_name=os.path.basename(debug_pdf),
                    mime="application/pdf",
                    use_container_width=True
                )



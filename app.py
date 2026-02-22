import streamlit as st
import tempfile
import os
import base64

from run_pipeline import run

st.set_page_config(
    page_title="Parts",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Parts Extractor — PDF → Excel")


# ======================================================
# PDF VIEWER FUNCTION
# ======================================================

def pdf_viewer(file_path, height=900):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode("utf-8")

    pdf_display = f"""
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="{height}"
            style="border:none;"
        ></iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)


# ======================================================
# MAIN LAYOUT
# ======================================================

left, right = st.columns(2)


# ======================================================
# LEFT SIDE — UI
# ======================================================

with left:

    uploaded_file = st.file_uploader(
        "Upload PDF Manual",
        type=["pdf"]
    )

    st.subheader("Project & Equipment Details (Optional)")

    col1, col2 = st.columns(2)

    vendor = col1.text_input("Vendor")
    model = col2.text_input("Model")

    project = col1.text_input("Project")
    subproject = col2.text_input("Sub Project")

    equipment = st.text_input("Equipment Name")

    vendor = vendor.strip() or None
    model = model.strip() or None
    project = project.strip() or None
    subproject = subproject.strip() or None
    equipment = equipment.strip() or None

    # ------------------------------
    # PAGE SELECTION
    # ------------------------------

    st.subheader("Page Selection")

    mode = st.radio(
        "Choose mode",
        ["All pages", "Page range", "Specific pages"]
    )

    pages = None

    if mode == "Page range":

        c1, c2 = st.columns(2)

        start_page = c1.number_input("Start Page", min_value=1, value=1)
        end_page = c2.number_input("End Page", min_value=1, value=1)

        if start_page <= end_page:
            pages = list(range(start_page, end_page + 1))
        else:
            st.error("Start page must be ≤ End page")

    elif mode == "Specific pages":

        page_input = st.text_input(
            "Enter pages (comma-separated)",
            placeholder="e.g. 1,3,5,8"
        )

        if page_input:
            try:
                pages = sorted({
                    int(p.strip())
                    for p in page_input.split(",")
                    if p.strip()
                })
            except:
                st.error("Invalid page numbers")

    # ------------------------------
    # OPTIONS
    # ------------------------------

    st.subheader("Options")

    debug = st.checkbox(
        "Generate debug overlay PDF",
        value=False
    )

    # ==================================================
    # RUN BUTTON (ALWAYS VISIBLE)
    # ==================================================

    run_clicked = st.button(
        "🚀 Run Extraction",
        use_container_width=True
    )


# ======================================================
# PROCESSING (OUTSIDE COLUMN — IMPORTANT)
# ======================================================

if run_clicked:

    if not uploaded_file:
        st.error("Please upload a PDF file")
        st.stop()

    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, uploaded_file.name)

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

    # Save outputs in session_state
    st.session_state["output_xlsx"] = output_xlsx

    if debug:
        debug_pdf = pdf_path.replace(".pdf", "_debug.pdf")
        if os.path.exists(debug_pdf):
            st.session_state["debug_pdf"] = debug_pdf


# ======================================================
# DOWNLOAD BUTTON (LEFT SIDE)
# ======================================================

with left:

    if "output_xlsx" in st.session_state:

        with open(st.session_state["output_xlsx"], "rb") as f:
            st.download_button(
                "⬇️ Download Excel Output",
                f,
                file_name=os.path.basename(st.session_state["output_xlsx"]),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )


# ======================================================
# RIGHT SIDE — DEBUG VIEWER
# ======================================================

with right:

    st.subheader("🔍 Debug PDF Viewer")

    if "debug_pdf" in st.session_state:
        pdf_viewer(st.session_state["debug_pdf"])
    else:
        st.info("Run extraction with debug enabled to view PDF")

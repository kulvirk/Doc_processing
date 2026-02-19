import streamlit as st
import tempfile
import os
from run_pipeline import run   # <-- change to your file name

st.title("Parts Extractor — PDF → Excel")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

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

debug = st.checkbox("Debug Mode", value=False)

if st.button("Run Extraction"):

    if not uploaded_file:
        st.error("Please upload a PDF")
        st.stop()

    if start_page > end_page:
        st.error("Start page must be ≤ End page")
        st.stop()

    # ----------------------------
    # Save uploaded file temporarily
    # ----------------------------
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    ) as tmp:

        tmp.write(uploaded_file.read())
        pdf_path = tmp.name

    output_csv = pdf_path.replace(".pdf", ".csv")

    pages = list(range(start_page, end_page + 1))

    with st.spinner("Processing PDF..."):

        output_xlsx = run(
            pdf_path=pdf_path,
            output_csv=output_csv,
            debug=debug,
            pages=pages
        )

    st.success("Extraction complete!")

    # ----------------------------
    # Download button
    # ----------------------------
    with open(output_xlsx, "rb") as f:
        st.download_button(
            "Download Excel",
            f,
            file_name=os.path.basename(output_xlsx),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


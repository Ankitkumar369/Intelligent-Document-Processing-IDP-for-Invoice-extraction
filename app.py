import streamlit as st
import pandas as pd
import pdfplumber
import json
import tempfile
import time
from pathlib import Path

from src.extraction.multiline_handler import MultilineHandler
from src.entity.entity_extractor import EntityExtractor
from src.normalization.normalizer import Normalizer
from src.validation.validator import Validator
from src.scoring.confidence_scorer import ConfidenceScorer
from src.rag.rag_processor import RAGProcessor

st.set_page_config(page_title="IDP Invoice System", layout="wide")

DOLLAR = chr(36)

@st.cache_resource
def get_components():
    return {
        "multiline": MultilineHandler(),
        "entity": EntityExtractor(),
        "normalizer": Normalizer(),
        "validator": Validator(),
        "scorer": ConfidenceScorer(),
        "rag": RAGProcessor(),
    }

comp = get_components()


def process_pdf(filepath, filename):
    with pdfplumber.open(filepath) as pdf:
        text = pdf.pages[0].extract_text() or ""
    items_r = comp["multiline"].extract_items(filepath)
    entities = comp["entity"].extract(text, filename, items_r.items)
    normalized = comp["normalizer"].normalize(entities, filename)
    report = comp["validator"].validate(normalized, filename)
    doc_score = comp["scorer"].score(normalized, report, entities.confidence, 1.0)
    return normalized, report, doc_score


def normalized_to_dict(normalized, report, doc_score):
    return {
        "filename": normalized.filename,
        "invoice_no": normalized.invoice_no,
        "date": normalized.date_normalized,
        "order_id": normalized.order_id,
        "customer_name": normalized.customer_name,
        "ship_mode": normalized.ship_mode,
        "currency": normalized.currency,
        "subtotal": normalized.subtotal,
        "discount": normalized.discount,
        "shipping": normalized.shipping,
        "total": normalized.total,
        "balance_due": normalized.balance_due,
        "item_count": len(normalized.items),
        "validation_passed": report.passed,
        "validation_score": report.score,
        "confidence_score": doc_score.overall_score,
        "confidence_label": doc_score.overall_label,
    }


st.title("Intelligent Document Processing - Invoice System")
st.caption("Upload SuperStore invoice PDFs and get structured, validated, confidence-scored data.")

tab1, tab2, tab3 = st.tabs(["Single Invoice", "Bulk Processing", "Dashboard"])

with tab1:
    st.subheader("Upload a single invoice PDF")
    single_file = st.file_uploader("Choose a PDF", type=["pdf"], key="single")

    if single_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(single_file.read())
            tmp_path = tmp.name

        with st.spinner("Processing invoice..."):
            normalized, report, doc_score = process_pdf(tmp_path, single_file.name)

        col1, col2, col3 = st.columns(3)
        col1.metric("Confidence Score", f"{doc_score.overall_score:.2f}", doc_score.overall_label)
        col2.metric("Validation", "PASSED" if report.passed else "FAILED")
        col3.metric("Total Amount", DOLLAR + f"{normalized.total:,.2f}")

        st.markdown("### Extracted Fields")
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Invoice No:** {normalized.invoice_no}")
            st.write(f"**Date:** {normalized.date_normalized}")
            st.write(f"**Customer:** {normalized.customer_name}")
            st.write(f"**Order ID:** {normalized.order_id}")
        with c2:
            st.write("**Subtotal:** " + DOLLAR + f"{normalized.subtotal:,.2f}")
            st.write("**Discount:** " + DOLLAR + f"{normalized.discount:,.2f} ({normalized.discount_pct}%)")
            st.write("**Shipping:** " + DOLLAR + f"{normalized.shipping:,.2f}")
            st.write("**Balance Due:** " + DOLLAR + f"{normalized.balance_due:,.2f}")

        if normalized.items:
            st.markdown("### Line Items")
            st.dataframe(pd.DataFrame(normalized.items), use_container_width=True)

        if report.issues:
            st.markdown("### Validation Issues")
            for issue in report.issues:
                st.warning(f"[{issue.severity.upper()}] {issue.field}: {issue.message}")

        result_dict = normalized_to_dict(normalized, report, doc_score)
        result_dict["items"] = normalized.items
        json_bytes = json.dumps(result_dict, indent=2).encode("utf-8")

        st.download_button(
            "Download JSON",
            data=json_bytes,
            file_name=f"{Path(single_file.name).stem}.json",
            mime="application/json",
        )

with tab2:
    st.subheader("Upload multiple invoice PDFs")
    bulk_files = st.file_uploader(
        "Choose PDFs", type=["pdf"], accept_multiple_files=True, key="bulk"
    )

    if bulk_files:
        st.write(f"**{len(bulk_files)} files selected**")

        if st.button("Process All Files"):
            progress = st.progress(0)
            status_text = st.empty()
            results = []
            start = time.time()

            for i, f in enumerate(bulk_files):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(f.read())
                    tmp_path = tmp.name

                try:
                    normalized, report, doc_score = process_pdf(tmp_path, f.name)
                    results.append(normalized_to_dict(normalized, report, doc_score))
                except Exception as e:
                    results.append({"filename": f.name, "error": str(e)})

                progress.progress((i + 1) / len(bulk_files))
                status_text.text(f"Processing {i+1}/{len(bulk_files)}: {f.name}")

            elapsed = round(time.time() - start, 2)
            status_text.text(f"Done in {elapsed}s")

            df = pd.DataFrame(results)
            st.session_state["bulk_results"] = df

            st.dataframe(df, use_container_width=True)

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download CSV",
                data=csv_bytes,
                file_name="bulk_invoices_extracted.csv",
                mime="text/csv",
            )

with tab3:
    st.subheader("Processing Analytics")

    if "bulk_results" in st.session_state and not st.session_state["bulk_results"].empty:
        df = st.session_state["bulk_results"]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Invoices", len(df))
        if "validation_passed" in df.columns:
            passed = df["validation_passed"].sum()
            col2.metric("Passed Validation", int(passed))
        if "total" in df.columns:
            col3.metric("Total Revenue", DOLLAR + f"{df['total'].sum():,.2f}")
        if "confidence_score" in df.columns:
            col4.metric("Avg Confidence", f"{df['confidence_score'].mean():.2f}")

        c1, c2 = st.columns(2)
        with c1:
            if "confidence_label" in df.columns:
                st.markdown("**Confidence Distribution**")
                st.bar_chart(df["confidence_label"].value_counts())
        with c2:
            if "ship_mode" in df.columns:
                st.markdown("**Ship Mode Distribution**")
                st.bar_chart(df["ship_mode"].value_counts())

        if "date" in df.columns and "total" in df.columns:
            st.markdown("**Revenue Over Time**")
            try:
                df_sorted = df.dropna(subset=["date"]).sort_values("date")
                st.line_chart(df_sorted.set_index("date")["total"])
            except Exception:
                pass
    else:
        st.info("Process some invoices in the Bulk Processing tab to see analytics here.")

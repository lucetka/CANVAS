
# Copilot-Assisted Novelty Verifier via Alex Search
# simply copied stReviewNoveltyCheckerAlex_2.py and then changed header text to "CANVAS" , added icon and the brief workflow description


import io
import time
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st


# ============================================================
# CONFIG
# ============================================================


import streamlit as st

st.set_page_config(page_title="CANVAS", page_icon="🎨", layout="wide")

st.title("🎨 CANVAS")
st.subheader("**C**opilot-**A**ssisted **N**ovelty **V**erifier via Open**A**lex **S**earch")
st.markdown(
    """
    ---
    ### 🔄 Workflow Pipeline
    1. **Copilot Prep:** Upload your step 2 output (the one with generated OpenAlex queries).
    2. **Novelty Check:** Press the Fetch button under the loaded dataset and CANVAS instantly performs all the OpenAlex queries and presents an enriched version of the input file. 
    3. **IF YOU SEE ANY ERRORS, PLEASE ENTER YOUR OPENALEX API KEY** (optional) and re-run the queries.   
    ---
    """
)




OPENALEX_BASE = "https://api.openalex.org/works"

QUERY_SHEET = "OpenAlex Queries"

REQUIRED_COLUMNS = [
    "Topic_ID",
    "Topic",
    "Description",
    "Suggested_Angle",
    "Query_Type",
    "Title_Search_Expression",
]


# ============================================================
# HELPERS
# ============================================================

def load_workbook(uploaded_file):
    """Read all sheets and return {sheet_name: dataframe}."""
    uploaded_file.seek(0)
    return pd.read_excel(
        uploaded_file,
        sheet_name=None,
        engine="openpyxl",
    )


def validate_query_sheet(df):
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    if missing:
        raise ValueError(
            "The 'OpenAlex Queries' sheet is missing required columns: "
            + ", ".join(missing)
        )


def reconstruct_abstract(inverted_index):
    """Convert OpenAlex abstract_inverted_index to readable text."""
    if not isinstance(inverted_index, dict) or not inverted_index:
        return None

    words = []

    for word, positions in inverted_index.items():
        if not isinstance(positions, list):
            continue

        for position in positions:
            words.append((position, word))

    words.sort(key=lambda x: x[0])

    return " ".join(word for _, word in words)


def extract_journal(work):
    try:
        return work["primary_location"]["source"]["display_name"]
    except (TypeError, KeyError):
        return None


def extract_landing_page(work):
    try:
        return work["primary_location"]["landing_page_url"]
    except (TypeError, KeyError):
        return None


def extract_authors(work):
    names = []

    for authorship in work.get("authorships", []) or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")

        if name:
            names.append(name)

    return "; ".join(names) if names else None


def query_openalex(
    search_expression,
    abstract_expression=None,   # NEW
    api_key=None,
    from_date="2024-01-01",
    per_page=25,
    timeout=60,
):
    """
    Run one OpenAlex title-only novelty query.
    Returns total match count, result records, and a safe request URL.
    """

    filter_parts = [
        "type:review",
        f"from_publication_date:{from_date}",
        f"title.search:{search_expression}",
    ]

    if abstract_expression:
        filter_parts.append(f"abstract.search:{abstract_expression}")

    filter_text = ",".join(filter_parts)

    params = {
        "filter": filter_text,
        "per_page": str(per_page),
        "select": (
            "id,doi,display_name,publication_year,"
            "publication_date,cited_by_count,"
            "primary_location,authorships,"
            "abstract_inverted_index"
        ),
    }

    if api_key and api_key.strip():
        params["api_key"] = api_key.strip()

    response = requests.get(
        OPENALEX_BASE,
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": "OpenAlex-Novelty-Checker/0.1",
        },
        timeout=timeout,
    )

    response.raise_for_status()
    payload = response.json()

    total_matches = payload.get("meta", {}).get("count", 0)
    results = payload.get("results", [])

    # Never expose the API key in the UI or exported workbook
    safe_request_url = response.url
    if api_key and api_key.strip():
        safe_request_url = safe_request_url.replace(
            api_key.strip(),
            "[REDACTED]"
        )

    return total_matches, results, safe_request_url

def run_queries(query_df, api_key=None, from_date="2024-01-01"):
    output_rows = []
    status_rows = []

    progress = st.progress(0)
    status_text = st.empty()

    total_queries = len(query_df)

    for i, (_, query_row) in enumerate(query_df.iterrows(), start=1):

        topic_id = str(query_row["Topic_ID"])
        topic = str(query_row["Topic"])
        query_type = str(query_row["Query_Type"])
        search_expression = str(query_row["Title_Search_Expression"])

        abstract_value = query_row.get("Abstract_Search_Expression")

        abstract_expression = (
            str(abstract_value).strip()
            if pd.notna(abstract_value) and str(abstract_value).strip()
            else None
        )

        status_text.write(
            f"Running {i}/{total_queries}: "
            f"{topic_id} · {query_type}"
        )

        try:
          
            total_matches, works, request_url = query_openalex(
                search_expression=search_expression,
                abstract_expression=abstract_expression,   # NEW
                api_key=api_key,
                from_date=from_date,
            )

            status_rows.append(
                {
                    "Topic_ID": topic_id,
                    "Topic": topic,
                    "Query_Type": query_type,
                    "Title_Search_Expression": search_expression,
                    "Abstract_Search_Expression": abstract_expression,
                    "Total_OpenAlex_Matches": total_matches,
                    "Returned_Results": len(works),
                    "Status": "Success",
                    "Error": None,
                    "Request_URL": request_url,
                }
            )

            for work in works:

                output_rows.append(
                    {
                        "Topic_ID": topic_id,
                        "Topic": topic,
                        "Description": query_row["Description"],
                        "Suggested_Angle": query_row["Suggested_Angle"],
                        "Query_Type": query_type,
                        "Title_Search_Expression": search_expression,
                        "Abstract_Search_Expression": abstract_expression,
                        "Total_OpenAlex_Matches": total_matches,
                        "Publication_Year": work.get("publication_year"),
                        "Publication_Date": work.get("publication_date"),
                        "Title": work.get("display_name"),
                        "Journal": extract_journal(work),
                        "Authors": extract_authors(work),
                        "DOI": work.get("doi"),
                        "Cited_By_Count": work.get("cited_by_count"),
                        "OpenAlex_ID": work.get("id"),
                        "Landing_Page_URL": extract_landing_page(work),
                        "Abstract": reconstruct_abstract(
                            work.get("abstract_inverted_index")
                        ),
                    }
                )

        except Exception as exc:

            status_rows.append(
                {
                    "Topic_ID": topic_id,
                    "Topic": topic,
                    "Query_Type": query_type,
                    "Title_Search_Expression": search_expression,
                    "Abstract_Search_Expression": abstract_expression,
                    "Total_OpenAlex_Matches": None,
                    "Returned_Results": 0,
                    "Status": "ERROR",
                    "Error": str(exc),
                    "Request_URL": None,
                }
            )

        progress.progress(i / total_queries)

        # Gentle pause between API calls
        time.sleep(0.1)

    status_text.empty()

    results_df = pd.DataFrame(output_rows)
    status_df = pd.DataFrame(status_rows)

    return results_df, status_df


def build_output_workbook(original_sheets, results_df, status_df):
    """
    Preserve the original workbook sheets and append/replace:
    - OpenAlex Results
    - OpenAlex Query Status
    """
    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        for sheet_name, df in original_sheets.items():

            # Do not retain stale versions of output sheets
            if sheet_name in {
                "OpenAlex Results",
                "OpenAlex Query Status",
            }:
                continue

            df.to_excel(
                writer,
                sheet_name=sheet_name[:31],
                index=False,
            )

        status_df.to_excel(
            writer,
            sheet_name="OpenAlex Query Status",
            index=False,
        )

        results_df.to_excel(
            writer,
            sheet_name="OpenAlex Results",
            index=False,
        )

    output.seek(0)

    return output


# ============================================================
# UI
# ============================================================

st.title("🔎 OpenAlex Review Novelty Check")

st.caption(
    "Upload the commissioning workbook, run the prepared "
    "OpenAlex title queries, and download the enriched workbook."
)

uploaded_file = st.file_uploader(
    "Upload Step-2 commissioning workbook",
    type=["xlsx"],
)

api_key = st.text_input(
    "OpenAlex API key (optional)",
    type="password",
    help="Leave blank to try without a key.",
)

from_date = st.text_input(
    "Review search start date",
    value="2024-01-01",
)


# ============================================================
# LOAD + PREVIEW
# ============================================================

if uploaded_file is not None:

    try:
        sheets = load_workbook(uploaded_file)

    except Exception as exc:
        st.error(f"Could not read workbook: {exc}")
        st.stop()

    st.success(
        f"Workbook loaded: {len(sheets)} worksheet(s)"
    )

    sheet_names = list(sheets.keys())

    st.write("**Worksheets found:**")
    st.write(", ".join(sheet_names))

    if QUERY_SHEET not in sheets:
        st.error(
            f'Required worksheet "{QUERY_SHEET}" was not found.'
        )
        st.stop()

    query_df = sheets[QUERY_SHEET].copy()

    try:
        validate_query_sheet(query_df)

    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    st.subheader("OpenAlex queries")

    st.dataframe(
        query_df,
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Preview other workbook sheets"):

        preview_sheet = st.selectbox(
            "Worksheet",
            sheet_names,
        )

        st.dataframe(
            sheets[preview_sheet],
            use_container_width=True,
            hide_index=True,
        )

    st.info(
        f"{len(query_df)} OpenAlex searches will be run. "
        "A maximum of 25 records will be retrieved per search."
    )


    # ========================================================
    # RUN
    # ========================================================

    if st.button(
        "Fetch OpenAlex review results",
        type="primary",
    ):

        results_df, status_df = run_queries(
            query_df=query_df,
            api_key=api_key,
            from_date=from_date,
        )

        st.session_state["oa_results"] = results_df
        st.session_state["oa_status"] = status_df
        st.session_state["original_sheets"] = sheets


# ============================================================
# RESULTS
# ============================================================

if "oa_status" in st.session_state:

    status_df = st.session_state["oa_status"]
    results_df = st.session_state["oa_results"]

    st.divider()

    st.subheader("Query status")

    st.dataframe(
        status_df,
        use_container_width=True,
        hide_index=True,
    )

    successful = (status_df["Status"] == "Success").sum()
    failed = (status_df["Status"] == "ERROR").sum()

    col1, col2, col3 = st.columns(3)

    col1.metric("Queries", len(status_df))
    col2.metric("Successful", successful)
    col3.metric("Errors", failed)

    st.subheader("OpenAlex results")

    if results_df.empty:

        st.warning(
            "The queries completed but no OpenAlex results were returned."
        )

    else:

        st.write(
            f"Retrieved **{len(results_df):,} records**."
        )

        st.dataframe(
            results_df,
            use_container_width=True,
            hide_index=True,
        )

        output_file = build_output_workbook(
            original_sheets=st.session_state["original_sheets"],
            results_df=results_df,
            status_df=status_df,
        )

        st.download_button(
            label="⬇️ Download enriched workbook",
            data=output_file,
            file_name="commissioning_openalex_enriched.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            type="primary",
        )
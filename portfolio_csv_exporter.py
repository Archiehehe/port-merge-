
import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from fpdf import FPDF
import pdfplumber

st.set_page_config(page_title="📊 Portfolio Merger", layout="centered")
st.title("📊 Portfolio Merger & Exporter")
st.markdown("Upload multiple portfolio files to merge holdings by symbol. Supports `.csv`, `.xlsx`, `.xls`, `.pdf`.")

export_format = st.selectbox("Output Format", ["Seeking Alpha Format", "Original Format (Cleaned)"])
uploaded_files = st.file_uploader("Upload Portfolio Files", type=["xlsx", "xls", "csv", "pdf"], accept_multiple_files=True)
purchase_date = st.date_input("Set Purchase Date (for Seeking Alpha export)", date.today())

# PDF utility
def generate_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt="Merged Portfolio", ln=True, align='C')
    pdf.ln(10)
    headers = df.columns.tolist()
    col_widths = [40, 40, 40, 40]
    for header in headers:
        pdf.cell(col_widths[0], 10, header, border=1)
    pdf.ln()
    for _, row in df.iterrows():
        for value in row:
            pdf.cell(col_widths[0], 10, str(value), border=1)
        pdf.ln()
    pdf_output_bytes = pdf.output(dest='S').encode('latin1')
    return BytesIO(pdf_output_bytes)

def extract_data(df):
    rename_map = {}
    for col in df.columns:
        col_l = col.lower()
        if 'ticker' in col_l:
            rename_map[col] = 'symbol'
        elif 'share' in col_l or 'quantity' in col_l:
            rename_map[col] = 'quantity'
        elif 'cost' in col_l:
            rename_map[col] = 'cost'
    df = df.rename(columns=rename_map)
    if {'symbol', 'quantity', 'cost'}.issubset(df.columns):
        df = df[['symbol', 'quantity', 'cost']].dropna()
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
        df['cost'] = pd.to_numeric(df['cost'], errors='coerce')
        return df.dropna()
    return None

final_data = []

if uploaded_files:
    for file in uploaded_files:
        try:
            if file.name.endswith('.csv'):
                raw = pd.read_csv(file)
            elif file.name.endswith('.pdf'):
                tables = []
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages:
                        tbl = page.extract_table()
                        if tbl:
                            tables.append(pd.DataFrame(tbl[1:], columns=tbl[0]))
                raw = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
            else:
                raw = pd.read_excel(file)
            df = extract_data(raw)
            if df is not None:
                final_data.append(df)
            else:
                st.warning(f"⚠️ File skipped (columns not found): {file.name}")
        except Exception as e:
            st.error(f"❌ Error processing {file.name}: {e}")

    if final_data:
        merged = pd.concat(final_data)
        merged = merged.groupby('symbol').apply(
            lambda x: pd.Series({
                'quantity': x['quantity'].sum(),
                'cost': (x['quantity'] * x['cost']).sum() / x['quantity'].sum()
            })
        ).reset_index()

        if export_format == "Seeking Alpha Format":
            merged['date'] = purchase_date.strftime('%Y-%m-%d')
            columns = ['symbol', 'quantity', 'cost', 'date']
        else:
            columns = ['symbol', 'quantity', 'cost']

        output_df = merged[columns]

        st.dataframe(output_df, use_container_width=True)

        st.download_button("⬇️ Download CSV", output_df.to_csv(index=False).encode('utf-8'),
                           "merged_portfolio.csv", "text/csv")

        excel = BytesIO()
        output_df.to_excel(excel, index=False)
        st.download_button("⬇️ Download Excel", excel.getvalue(),
                           "merged_portfolio.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        pdf_file = generate_pdf(output_df)
        st.download_button("⬇️ Download PDF", pdf_file, "merged_portfolio.pdf", "application/pdf")
    else:
        st.warning("⚠️ No valid portfolio files were uploaded.")


import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from fpdf import FPDF
import pdfplumber

st.set_page_config(page_title="Portfolio Merger", layout="centered")
st.title("📊 Portfolio Merger")

st.markdown("""
Upload multiple portfolios and combine everything.
Supports `.csv`, `.xlsx`, `.xls`, `.pdf`
""")

export_format = st.selectbox("Output Format", ["Seeking Alpha Format", "Original Format (Cleaned)"])
uploaded_files = st.file_uploader("Upload Portfolio Files", type=["xlsx", "xls", "csv", "pdf"], accept_multiple_files=True)
purchase_date = st.date_input("Set Purchase Date (for Seeking Alpha export)", date.today())

def generate_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt="Merged Portfolio", ln=True, align='C')
    pdf.ln(10)
    for header in df.columns:
        pdf.cell(40, 10, header, border=1)
    pdf.ln()
    for _, row in df.iterrows():
        for val in row:
            pdf.cell(40, 10, str(val), border=1)
        pdf.ln()
    return BytesIO(pdf.output(dest='S').encode('latin1'))

def repair_pdf_headers(columns):
    joined = ' '.join(columns).replace('\n', ' ')
    if 'Total Shares Held' in joined:
        return ['Name', 'Ticker', 'Total Shares Held', 'Current Price (USD)',
                'Current Value (USD)', 'Average Cost (USD)', 'Total Amount Invested (USD)',
                'Investment Returns (USD)', 'Investment Returns (%)',
                'Daily Change (USD)', 'Daily Change (%)']
    return columns

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
        elif 'price' in col_l and 'current' in col_l:
            rename_map[col] = 'price'
    df = df.rename(columns=rename_map)
    if 'symbol' not in df.columns:
        return None
    for col in ['quantity', 'cost', 'price']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

dataframes = []
skipped_files = []
skipped_tickers = []

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
                            headers = repair_pdf_headers(tbl[0])
                            cleaned = pd.DataFrame(tbl[1:], columns=headers if len(headers) == len(tbl[0]) else tbl[0])
                            tables.append(cleaned)
                raw = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
            else:
                raw = pd.read_excel(file)
            raw.columns = raw.columns.str.strip()
            df = extract_data(raw)
            if df is not None:
                dataframes.append(df)
            else:
                skipped_files.append(file.name)
        except Exception as e:
            skipped_files.append(file.name)

    if dataframes:
        combined = pd.concat(dataframes, ignore_index=True)

        # Ticker-wise validation
        original_tickers = combined['symbol'].nunique()
        combined = combined.groupby('symbol').agg({
            'quantity': 'sum',
            'cost': lambda x: (x * combined.loc[x.index, 'quantity']).sum() / combined.loc[x.index, 'quantity'].sum() if x.notna().any() and combined.loc[x.index, 'quantity'].notna().any() else None,
            'price': 'mean' if 'price' in combined.columns else 'first'
        }).reset_index()

        final_tickers = combined['symbol'].nunique()
        if final_tickers < original_tickers:
            st.warning(f"⚠️ {original_tickers - final_tickers} tickers may have been skipped due to merge issues.")

        combined['invested'] = combined['quantity'] * combined['cost']
        if 'price' in combined.columns:
            combined['value'] = combined['quantity'] * combined['price']
            if combined['value'].notna().any():
                total_value = combined['value'].sum()
                invested_total = combined['invested'].sum()
                pnl = total_value - invested_total
                pnl_pct = pnl / invested_total * 100 if invested_total else 0
                st.info(f"💰 Total Value: ${total_value:,.2f} | Invested: ${invested_total:,.2f} | P&L: ${pnl:,.2f} ({pnl_pct:.2f}%)")

        base = ['symbol', 'quantity', 'cost']
        if export_format == "Seeking Alpha Format":
            combined['date'] = purchase_date.strftime('%Y-%m-%d')
            out = base + ['date']
        else:
            out = base + ['invested']
            if 'value' in combined:
                out.append('value')

        st.dataframe(combined[out], use_container_width=True)

        st.download_button("⬇️ CSV", combined[out].to_csv(index=False).encode("utf-8"), "merged_pdf_safe.csv", "text/csv")
        excel = BytesIO(); combined[out].to_excel(excel, index=False)
        st.download_button("⬇️ Excel", excel.getvalue(), "merged_pdf_safe.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("⬇️ PDF", generate_pdf(combined[out]), "merged_pdf_safe.pdf", "application/pdf")

    if skipped_files:
        st.warning("Some files or tickers were skipped due to malformed structure: " + ", ".join(skipped_files))

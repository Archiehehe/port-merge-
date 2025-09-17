
import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from fpdf import FPDF
import pdfplumber

st.set_page_config(page_title="Portfolio Merger (Preserve All)", layout="centered")
st.title("📊 Portfolio Merger with All Tickers Preserved")

st.markdown("""
Uploads multiple portfolio files and merges them by ticker symbol — even if some rows have missing quantity or cost.

✅ Supports `.csv`, `.xlsx`, `.xls`, `.pdf`  
✅ Includes all tickers  
✅ Shows total invested and value (when possible)
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
    headers = df.columns.tolist()
    for header in headers:
        pdf.cell(40, 10, str(header), border=1)
    pdf.ln()
    for _, row in df.iterrows():
        for val in row:
            pdf.cell(40, 10, str(val), border=1)
        pdf.ln()
    return BytesIO(pdf.output(dest='S').encode('latin1'))

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
    usable = ['symbol'] + [col for col in ['quantity', 'cost', 'price'] if col in df.columns]
    df = df[usable]
    for col in ['quantity', 'cost', 'price']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

dataframes = []

if uploaded_files:
    for file in uploaded_files:
        try:
            if file.name.endswith('.csv'):
                raw = pd.read_csv(file)
            elif file.name.endswith('.pdf'):
                tables = []
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages:
                        table = page.extract_table()
                        if table:
                            tables.append(pd.DataFrame(table[1:], columns=table[0]))
                raw = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
            else:
                raw = pd.read_excel(file)
            df = extract_data(raw)
            dataframes.append(df)
        except Exception as e:
            st.warning(f"⚠️ Could not load {file.name}: {e}")

    if dataframes:
        full_df = pd.concat(dataframes, ignore_index=True)
        merged = full_df.groupby('symbol').agg({
            'quantity': 'sum',
            'cost': lambda x: (x * full_df.loc[x.index, 'quantity']).sum() / full_df.loc[x.index, 'quantity'].sum() if x.notna().any() and full_df.loc[x.index, 'quantity'].notna().any() else None,
            'price': 'mean' if 'price' in full_df.columns else 'first'
        }).reset_index()

        merged['invested'] = merged['quantity'] * merged['cost']
        if 'price' in merged.columns:
            merged['value'] = merged['quantity'] * merged['price']

        # Show P&L if possible
        if 'value' in merged and merged['value'].notna().any():
            total_val = merged['value'].sum()
            total_inv = merged['invested'].sum()
            pnl = total_val - total_inv
            pnl_pct = pnl / total_inv * 100 if total_inv else 0
            st.info(f"💰 Total Value: ${total_val:,.2f} | Invested: ${total_inv:,.2f} | P&L: ${pnl:,.2f} ({pnl_pct:.2f}%)")

        # Output columns
        base_cols = ['symbol', 'quantity', 'cost']
        if export_format == "Seeking Alpha Format":
            merged['date'] = purchase_date.strftime('%Y-%m-%d')
            out_cols = base_cols + ['date']
        else:
            out_cols = base_cols + ['invested']
            if 'value' in merged:
                out_cols.append('value')

        output = merged[out_cols]
        st.dataframe(output, use_container_width=True)

        st.download_button("⬇️ CSV", output.to_csv(index=False).encode("utf-8"), "merged_preserved.csv", "text/csv")
        xlsx = BytesIO(); output.to_excel(xlsx, index=False)
        st.download_button("⬇️ Excel", xlsx.getvalue(), "merged_preserved.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("⬇️ PDF", generate_pdf(output), "merged_preserved.pdf", "application/pdf")

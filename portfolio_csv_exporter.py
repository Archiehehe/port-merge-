
import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from fpdf import FPDF

st.set_page_config(page_title="Portfolio Merger", layout="centered")
st.title("📊 Portfolio Merger - Clean Output")

uploaded_files = st.file_uploader("Upload Portfolio Files (CSV/XLSX only)", type=["xlsx", "xls", "csv"], accept_multiple_files=True)
purchase_date = st.date_input("Purchase Date (for Seeking Alpha)", date.today())

class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Merged Portfolio Report", ln=True, align="C")
        self.ln(5)

    def table(self, data):
        self.set_font("Arial", size=10)
        col_width = (self.w - 2 * self.l_margin) / len(data.columns)
        for col in data.columns:
            self.cell(col_width, 10, col, border=1)
        self.ln()
        for _, row in data.iterrows():
            for val in row:
                self.cell(col_width, 10, str(val), border=1)
            self.ln()

    def summary(self, total, invested):
        pnl = total - invested
        pnl_pct = pnl / invested * 100 if invested else 0
        self.ln(5)
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, f"Total Value: ${total:,.2f} | Invested: ${invested:,.2f} | P&L: ${pnl:,.2f} ({pnl_pct:.2f}%)", ln=True, align="C")

    def output_pdf(self, df):
        self.add_page()
        total = df["value"].sum()
        invested = df["invested"].sum()
        self.summary(total, invested)
        self.table(df)
        buf = BytesIO()
        pdf_bytes = self.output(dest='S').encode('latin1')
        return BytesIO(pdf_bytes)

def extract_generic_data(df):
    df = df.rename(columns=lambda c: c.strip().lower())
    rename_map = {}
    for col in df.columns:
        if 'ticker' in col:
            rename_map[col] = 'symbol'
        elif 'share' in col or 'quantity' in col:
            rename_map[col] = 'quantity'
        elif 'cost' in col:
            rename_map[col] = 'cost'
        elif 'value' in col and 'current' in col:
            rename_map[col] = 'value'
    df = df.rename(columns=rename_map)
    for col in ['quantity', 'cost', 'value']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    if 'symbol' not in df.columns:
        return None
    return df[['symbol', 'quantity', 'cost', 'value']].dropna(subset=["symbol"])

frames = []

if uploaded_files:
    for f in uploaded_files:
        try:
            if f.name.endswith(".csv"):
                df = extract_generic_data(pd.read_csv(f))
            else:
                df = extract_generic_data(pd.read_excel(f))
            if df is not None:
                frames.append(df)
            else:
                st.warning(f"⚠️ Could not extract data from: {f.name}")
        except Exception as e:
            st.error(f"❌ {f.name} failed: {e}")

    if frames:
        all_data = pd.concat(frames, ignore_index=True)
        all_data["invested"] = all_data["quantity"] * all_data["cost"]
        all_data["value"] = all_data["value"].fillna(all_data["invested"])

        combined = all_data.groupby("symbol", as_index=False).agg({
            "quantity": "sum",
            "cost": "mean",
            "invested": "sum",
            "value": "sum"
        })

        st.dataframe(combined, use_container_width=True)

        pdf = PDFReport()
        pdf_file = pdf.output_pdf(combined)
        st.download_button("⬇️ Download PDF", pdf_file, "merged_portfolio.pdf", mime="application/pdf")

        st.download_button("⬇️ Download CSV", combined.to_csv(index=False).encode("utf-8"), "merged_portfolio.csv", mime="text/csv")

        xls = BytesIO()
        combined.to_excel(xls, index=False)
        st.download_button("⬇️ Download Excel", xls.getvalue(), "merged_portfolio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

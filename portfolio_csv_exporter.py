
import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import pdfplumber

st.set_page_config(page_title="Portfolio Merger - Final PDF Fix", layout="centered")
st.title("📊 Portfolio Merger (Final Fix for Vested PDF)")

export_format = st.selectbox("Output Format", ["Seeking Alpha Format", "Original Format (Cleaned)"])
uploaded_files = st.file_uploader("Upload Portfolio Files", type=["xlsx", "xls", "csv", "pdf"], accept_multiple_files=True)
purchase_date = st.date_input("Purchase Date (for Seeking Alpha)", date.today())

def generate_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt="Merged Portfolio", ln=True, align='C')
    pdf.ln(10)
    for col in df.columns:
        pdf.cell(40, 10, str(col), border=1)
    pdf.ln()
    for _, row in df.iterrows():
        for val in row:
            pdf.cell(40, 10, str(val), border=1)
        pdf.ln()
    return BytesIO(pdf.output(dest='S').encode('latin1'))

def generate_summary_image(df):
    df = df[df['value'].notna()]
    top = df.sort_values('value', ascending=False).head(5)
    labels = top['symbol']
    sizes = top['value']

    fig, ax = plt.subplots(figsize=(6, 6), dpi=150)
    plt.style.use("dark_background")

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        startangle=140,
        textprops=dict(color="white", fontsize=10, weight="bold"),
        wedgeprops=dict(width=0.4)
    )
    for t in texts + autotexts:
        t.set_path_effects([
            path_effects.Stroke(linewidth=2, foreground='black'),
            path_effects.Normal()
        ])
    total = df["value"].sum()
    invested = df["invested"].sum()
    pnl = total - invested
    pnl_pct = pnl / invested * 100 if invested else 0

    ax.text(0, 0.1, f"${total:,.0f}", ha='center', fontsize=18, color='cyan', weight='bold')
    ax.text(0, -0.1, f"{pnl:+,.0f} ({pnl_pct:.2f}%)", ha='center', fontsize=12, color='lime' if pnl >= 0 else 'red')
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", transparent=True)
    plt.close()
    buf.seek(0)
    return buf

def extract_vested_pdf(path):
    with pdfplumber.open(path) as pdf:
        table = pdf.pages[0].extract_table()
        headers = table[0]
        if "Total Shares" in headers and "Held" in headers:
            headers = [h if h != "Total Shares" else "Total Shares Held" for h in headers if h != "Held"]
        df = pd.DataFrame(table[1:], columns=headers)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        "Ticker": "symbol",
        "Total Shares Held": "quantity",
        "Average Cost (USD)": "cost",
        "Current Value (USD)": "value"
    })
    for col in ['quantity', 'cost', 'value']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df[['symbol', 'quantity', 'cost', 'value']].dropna(subset=["symbol"])

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
            if f.name.endswith(".pdf"):
                df = extract_vested_pdf(f)
            elif f.name.endswith(".csv"):
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
        all_data["value"] = all_data["value"].fillna(all_data["quantity"] * all_data["cost"])

        combined = all_data.groupby("symbol", as_index=False).agg({
            "quantity": "sum",
            "cost": "mean",
            "invested": "sum",
            "value": "sum"
        })

        if export_format == "Seeking Alpha Format":
            combined["date"] = purchase_date.strftime("%Y-%m-%d")
            output_cols = ["symbol", "quantity", "cost", "date"]
        else:
            output_cols = ["symbol", "quantity", "cost", "invested", "value"]

        st.dataframe(combined[output_cols], use_container_width=True)

        st.download_button("⬇️ CSV", combined[output_cols].to_csv(index=False).encode("utf-8"), "pdf_final_merged.csv")
        xls = BytesIO(); combined[output_cols].to_excel(xls, index=False); st.download_button("⬇️ Excel", xls.getvalue(), "pdf_final_merged.xlsx")
        st.download_button("⬇️ PDF", generate_pdf(combined[output_cols]), "pdf_final_merged.pdf", "application/pdf")
        st.download_button("📸 Summary Image", generate_summary_image(combined), "portfolio_summary_final.png", "image/png")
        pnl = combined["value"].sum() - combined["invested"].sum()
        pnl_pct = pnl / combined["invested"].sum() * 100 if combined["invested"].sum() else 0
        st.caption(f"💰 Total Value: ${combined['value'].sum():,.2f} | 📈 P&L: ${pnl:+,.2f} ({pnl_pct:.2f}%)")


import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from datetime import date
from io import BytesIO
from fpdf import FPDF
import pdfplumber

st.set_page_config(page_title="Portfolio Merger", layout="centered")
st.title("📊 Portfolio Merger")

export_format = st.selectbox("Output Format", ["Seeking Alpha Format", "Original Format"])
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

def generate_summary_image(df):
    df = df.copy()
    df = df[df['value'].notna()]
    top5 = df.sort_values('value', ascending=False).head(5)
    labels = top5['symbol']
    sizes = top5['value']

    total_value = df['value'].sum()
    pnl_dollars = df['value'].sum() - df['invested'].sum()
    pnl_percent = (pnl_dollars / df['invested'].sum()) * 100 if df['invested'].sum() else 0

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

    ax.set_title("💼 Portfolio Summary", fontsize=16, weight='bold', color="white", pad=20)

    value_text = ax.text(
        0, 0.1, f"${total_value:,.0f}",
        ha='center', va='center', fontsize=18, fontweight='bold',
        color="cyan"
    )
    value_text.set_path_effects([
        path_effects.Stroke(linewidth=3, foreground='black'),
        path_effects.Normal()
    ])

    pnl_color = "lime" if pnl_dollars >= 0 else "red"
    pnl_text = ax.text(
        0, -0.1, f"{pnl_dollars:+,.0f} ({pnl_percent:.2f}%)",
        ha='center', va='center', fontsize=13, fontweight='bold',
        color=pnl_color
    )
    pnl_text.set_path_effects([
        path_effects.Stroke(linewidth=2, foreground='black'),
        path_effects.Normal()
    ])

    buffer = BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png", bbox_inches="tight", transparent=True)
    plt.close()
    buffer.seek(0)
    return buffer

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
                st.warning(f"⚠️ Columns not found in {file.name}")
        except Exception as e:
            st.error(f"❌ Error reading {file.name}: {e}")

    if dataframes:
        combined = pd.concat(dataframes, ignore_index=True)

        combined = combined.groupby('symbol').agg({
            'quantity': 'sum',
            'cost': lambda x: (x * combined.loc[x.index, 'quantity']).sum() / combined.loc[x.index, 'quantity'].sum() if x.notna().any() and combined.loc[x.index, 'quantity'].notna().any() else None,
            'price': 'mean' if 'price' in combined.columns else 'first'
        }).reset_index()

        combined['invested'] = combined['quantity'] * combined['cost']
        if 'price' in combined.columns:
            combined['value'] = combined['quantity'] * combined['price']

        base = ['symbol', 'quantity', 'cost']
        if export_format == "Seeking Alpha Format":
            combined['date'] = purchase_date.strftime('%Y-%m-%d')
            out = base + ['date']
        else:
            out = base + ['invested']
            if 'value' in combined:
                out.append('value')

        st.dataframe(combined[out], use_container_width=True)

        st.download_button("⬇️ CSV", combined[out].to_csv(index=False).encode("utf-8"), "merged_final.csv", "text/csv")
        xlsx = BytesIO(); combined[out].to_excel(xlsx, index=False)
        st.download_button("⬇️ Excel", xlsx.getvalue(), "merged_final.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("⬇️ PDF", generate_pdf(combined[out]), "merged_final.pdf", "application/pdf")

        if 'value' in combined.columns:
            st.markdown("### 🖼️ Download Portfolio Summary Image")
            st.download_button("📸 Summary Image (PNG)", generate_summary_image(combined), "portfolio_summary.png", "image/png")

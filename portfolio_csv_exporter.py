
import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from PIL import Image

st.set_page_config(page_title="Portfolio Merger", layout="centered")

st.markdown("""<style>
body {
    background-color: #0e1117;
    color: #ffffff;
}
h1, h2, h3, h4, h5, h6 {
    color: #00ffe1;
}
.reportview-container .markdown-text-container {
    color: #ffffff;
}
.stDataFrame, .stTable {
    background-color: #1c1f26;
    color: white;
}
.css-1d391kg, .css-qrbaxs, .css-ffhzg2 {
    background-color: #1c1f26 !important;
    color: white !important;
}
</style>""", unsafe_allow_html=True)

st.title("📊 Portfolio Merger with P&L Summary + Chart")

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

    def summary(self, total, invested, image_path):
        pnl = total - invested
        pnl_pct = pnl / invested * 100 if invested else 0
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, f"Total Value: ${total:,.2f} | Invested: ${invested:,.2f} | P&L: ${pnl:,.2f} ({pnl_pct:.2f}%)", ln=True, align="C")
        self.ln(10)
        self.image(image_path, x=30, w=150)
        self.ln(10)

    def output_pdf(self, df, image_path):
        self.add_page()
        total = df["value"].sum()
        invested = df["invested"].sum()
        self.summary(total, invested, image_path)
        self.table(df)
        pdf_bytes = self.output(dest="S").encode("latin1")
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

        # 📘 Live blue box
        total = combined["value"].sum()
        invested = combined["invested"].sum()
        pnl = total - invested
        pnl_pct = (pnl / invested * 100) if invested else 0
        st.info(f"💰 **Value:** ${total:,.2f} | 🧾 **Invested:** ${invested:,.2f} | 📈 **P&L:** ${pnl:+,.2f} ({pnl_pct:.2f}%)")

        # 📸 Generate and preview summary image
        
def generate_summary_image():
    combined_sorted = combined.sort_values("value", ascending=False)
    top = combined_sorted.head(5)
    other_total = combined_sorted["value"].sum() - top["value"].sum()
    if other_total > 0:
        top = pd.concat([top, pd.DataFrame([{"symbol": "Other", "value": other_total}])], ignore_index=True)
    labels = top["symbol"]
    sizes = top["value"]

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
            path_effects.Stroke(linewidth=2, foreground="black"),
            path_effects.Normal()
        ])
    ax.text(0, 0.1, f"${total:,.0f}", ha="center", fontsize=18, color="cyan", weight="bold")
    ax.text(0, -0.1, f"{pnl:+,.0f} ({pnl_pct:.2f}%)", ha="center", fontsize=12, color="lime" if pnl >= 0 else "red")
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", transparent=True)
    plt.close()
    buf.seek(0)
    return buf

            combined_sorted = combined.sort_values("value", ascending=False)
top = combined_sorted.head(5)
other_total = combined_sorted["value"].sum() - top["value"].sum()
if other_total > 0:
    top = pd.concat([top, pd.DataFrame([{"symbol": "Other", "value": other_total}])], ignore_index=True)
            labels = top["symbol"]
            sizes = top["value"]
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
                    path_effects.Stroke(linewidth=2, foreground="black"),
                    path_effects.Normal()
                ])
            ax.text(0, 0.1, f"${total:,.0f}", ha="center", fontsize=18, color="cyan", weight="bold")
            ax.text(0, -0.1, f"{pnl:+,.0f} ({pnl_pct:.2f}%)", ha="center", fontsize=12, color="lime" if pnl >= 0 else "red")
            buf = BytesIO()
            plt.tight_layout()
            plt.savefig(buf, format="png", transparent=True)
            plt.close()
            buf.seek(0)
            return buf

        img_buf = generate_summary_image()
        with open("summary_temp.png", "wb") as f_img:
            f_img.write(img_buf.read())
        st.image("summary_temp.png", caption="📊 Portfolio Summary", use_container_width=True)

        # 📄 Generate and export PDF with image
        Image.open("summary_temp.png").convert("RGB").save("summary_temp_converted.jpg")
        pdf = PDFReport()
        pdf_file = pdf.output_pdf(combined, "summary_temp_converted.jpg")
        pdf_name = f"archie_portfolio_{date.today()}.pdf"
        st.download_button("⬇️ Download PDF", pdf_file, pdf_name, mime="application/pdf")

        # Other formats
        st.download_button("⬇️ Download CSV", combined.to_csv(index=False).encode("utf-8"), "merged_portfolio.csv", mime="text/csv")
        xlsx = BytesIO()
        combined.to_excel(xlsx, index=False)
        st.download_button("⬇️ Download Excel", xlsx.getvalue(), "merged_portfolio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("📸 Download Summary Image", open("summary_temp.png", "rb").read(), "portfolio_summary.png", "image/png")


import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from fpdf import FPDF
import pdfplumber

st.set_page_config(page_title="Portfolio Combiner & Exporter", layout="centered")
st.title("📈 Portfolio Combiner & Exporter")
st.markdown("""
Upload multiple portfolio files and get a combined output in **Excel**, **CSV**, or **PDF**.

Supports `.xlsx`, `.xls`, `.csv`, and `.pdf` formats.
""")

export_format = st.selectbox("Choose Output Format", ["Original Format (Combined)", "Seeking Alpha Format"])
uploaded_files = st.file_uploader("Upload Portfolio Files", type=["xlsx", "xls", "csv", "pdf"], accept_multiple_files=True)
purchase_date = st.date_input("Select Purchase Date (for Seeking Alpha export)", date.today())

def generate_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt="Combined Portfolio", ln=True, align='C')
    pdf.ln(10)

    col_widths = [40, 40, 40, 40]
    headers = df.columns.tolist()

    for i, header in enumerate(headers):
        pdf.cell(col_widths[i % len(col_widths)], 10, header, border=1)
    pdf.ln()

    for _, row in df.iterrows():
        for i, value in enumerate(row):
            pdf.cell(col_widths[i % len(col_widths)], 10, str(value), border=1)
        pdf.ln()

    pdf_output_bytes = pdf.output(dest='S').encode('latin1')
    output = BytesIO(pdf_output_bytes)
    return output

if uploaded_files:
    all_data = []

    for file in uploaded_files:
        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file)
                all_data.append(df)
            elif file.name.endswith(".pdf"):
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages:
                        table = page.extract_table()
                        if table:
                            temp_df = pd.DataFrame(table[1:], columns=table[0])
                            all_data.append(temp_df)
            else:
                df = pd.read_excel(file)
                all_data.append(df)
        except Exception as e:
            st.error(f"❌ Error reading {file.name}: {e}")

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df = combined_df.loc[:, ~combined_df.columns.str.contains('^Unnamed')]

        st.markdown("### 📊 Combined Portfolio Preview")
        st.dataframe(combined_df, use_container_width=True)

        if export_format == "Seeking Alpha Format":
            try:
                df_clean = combined_df[["Ticker", "Total Shares Held", "Average Cost (USD)"]].rename(columns={
                    "Ticker": "symbol",
                    "Total Shares Held": "quantity",
                    "Average Cost (USD)": "cost"
                })
                grouped_df = df_clean.groupby("symbol").apply(
                    lambda x: pd.Series({
                        "quantity": x["quantity"].astype(float).sum(),
                        "cost": (x["quantity"].astype(float) * x["cost"].astype(float)).sum() / x["quantity"].astype(float).sum()
                    })
                ).reset_index()
                grouped_df["date"] = purchase_date.strftime("%Y-%m-%d")
                final_df = grouped_df[["symbol", "quantity", "cost", "date"]]

                st.success("✅ Seeking Alpha format ready!")

                csv = final_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download as CSV", data=csv, file_name="seeking_alpha_portfolio.csv", mime="text/csv")

                excel = BytesIO()
                final_df.to_excel(excel, index=False)
                st.download_button("⬇️ Download as Excel", data=excel.getvalue(), file_name="seeking_alpha_portfolio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                pdf_file = generate_pdf(final_df)
                st.download_button("⬇️ Download as PDF", data=pdf_file, file_name="seeking_alpha_portfolio.pdf", mime="application/pdf")

            except Exception as e:
                st.error(f"⚠️ Failed to transform into Seeking Alpha format: {e}")

        else:
            try:
                expected_cols = {
                    "Ticker": "symbol",
                    "Total Shares
Held": "quantity",
                    "Current Price
(USD)": "price",
                    "Current Value
(USD)": "value",
                    "Average Cost
(USD)": "cost"
                }
                usable_cols = {col: name for col, name in expected_cols.items() if col in combined_df.columns}
                clean_df = combined_df[list(usable_cols.keys())].rename(columns=usable_cols)
                clean_df = clean_df.dropna(subset=["symbol"])

                st.success("✅ Cleaned and combined data ready")

                if {'value', 'cost', 'quantity'}.issubset(clean_df.columns):
                    clean_df = clean_df.astype({"value": float, "cost": float, "quantity": float})
                    invested = (clean_df["quantity"] * clean_df["cost"]).sum()
                    current = clean_df["value"].sum()
                    pnl = current - invested
                    pnl_pct = (pnl / invested) * 100 if invested != 0 else 0

                    st.info(f"**💰 Total Value:** ${current:,.2f}  |  **📈 All-Time P&L:** ${pnl:,.2f} ({pnl_pct:.2f}%)")

                csv = clean_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download as CSV", data=csv, file_name="combined_portfolio.csv", mime="text/csv")

                excel = BytesIO()
                clean_df.to_excel(excel, index=False)
                st.download_button("⬇️ Download as Excel", data=excel.getvalue(), file_name="combined_portfolio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                pdf_file = generate_pdf(clean_df)
                st.download_button("⬇️ Download as PDF", data=pdf_file, file_name="combined_portfolio.pdf", mime="application/pdf")

            except Exception as e:
                st.error(f"⚠️ Failed to process original format output: {e}")

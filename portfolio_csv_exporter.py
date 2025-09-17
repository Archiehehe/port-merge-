
import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO
from fpdf import FPDF
import pdfplumber

st.set_page_config(page_title="Portfolio Combiner & Exporter", layout="centered")
st.title("📈 Portfolio Combiner & Exporter")

st.markdown("""Upload `.csv`, `.xlsx`, `.xls`, or `.pdf` files to combine portfolios.

Choose to export in:
- **Original Format**: Keeps all available columns
- **Seeking Alpha Format**: Transforms into `symbol, quantity, cost, date`
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
        pdf.cell(col_widths[i % len(col_widths)], 10, str(header), border=1)
    pdf.ln()

    for _, row in df.iterrows():
        for i, value in enumerate(row):
            pdf.cell(col_widths[i % len(col_widths)], 10, str(value), border=1)
        pdf.ln()

    pdf_output_bytes = pdf.output(dest='S').encode('latin1')
    return BytesIO(pdf_output_bytes)

if uploaded_files:
    valid_dfs = []
    skipped = []

    for file in uploaded_files:
        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file)
            elif file.name.endswith(".pdf"):
                with pdfplumber.open(file) as pdf:
                    all_tables = []
                    for page in pdf.pages:
                        table = page.extract_table()
                        if table:
                            temp_df = pd.DataFrame(table[1:], columns=table[0])
                            all_tables.append(temp_df)
                    df = pd.concat(all_tables, ignore_index=True) if all_tables else pd.DataFrame()
            else:
                df = pd.read_excel(file)

            if not df.empty:
                df.columns = df.columns.map(lambda c: c.strip())
                valid_dfs.append(df)
            else:
                skipped.append(file.name)
        except Exception as e:
            skipped.append(file.name)

    if skipped:
        st.warning(f"⚠️ Skipped files due to errors or empty data: {', '.join(skipped)}")

    if valid_dfs:
        combined_df = pd.concat(valid_dfs, ignore_index=True)
        combined_df = combined_df.loc[:, ~combined_df.columns.str.contains('^Unnamed')]

        st.markdown("### 📊 Combined Portfolio Preview")
        st.dataframe(combined_df.head(50), use_container_width=True)

        if export_format == "Seeking Alpha Format":
            required_cols = ["Ticker", "Total Shares Held", "Average Cost (USD)"]
            if all(col in combined_df.columns for col in required_cols):
                try:
                    df_clean = combined_df[required_cols].rename(columns={
                        "Ticker": "symbol",
                        "Total Shares Held": "quantity",
                        "Average Cost (USD)": "cost"
                    })

                    df_clean = df_clean.dropna(subset=["symbol", "quantity", "cost"])
                    df_clean["quantity"] = df_clean["quantity"].astype(float)
                    df_clean["cost"] = df_clean["cost"].astype(float)

                    grouped_df = df_clean.groupby("symbol").apply(
                        lambda x: pd.Series({
                            "quantity": x["quantity"].sum(),
                            "cost": (x["quantity"] * x["cost"]).sum() / x["quantity"].sum()
                        })
                    ).reset_index()

                    grouped_df["date"] = purchase_date.strftime("%Y-%m-%d")
                    final_df = grouped_df[["symbol", "quantity", "cost", "date"]]

                    st.success("✅ Seeking Alpha format ready!")

                    st.download_button("⬇️ Download CSV", final_df.to_csv(index=False).encode("utf-8"),
                                       "seeking_alpha_portfolio.csv", "text/csv")

                    excel = BytesIO()
                    final_df.to_excel(excel, index=False)
                    st.download_button("⬇️ Download Excel", excel.getvalue(),
                                       "seeking_alpha_portfolio.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                    pdf_file = generate_pdf(final_df)
                    st.download_button("⬇️ Download PDF", pdf_file,
                                       "seeking_alpha_portfolio.pdf", "application/pdf")

                except Exception as e:
                    st.error(f"❌ Failed to create Seeking Alpha format: {e}")
            else:
                st.error("❌ One or more required columns missing for Seeking Alpha format.")

        else:
            clean_df = combined_df.copy()

            if {'Current Value\n(USD)', 'Average Cost\n(USD)', 'Total Shares\nHeld'}.issubset(clean_df.columns):
                try:
                    clean_df = clean_df.rename(columns={
                        'Current Value
(USD)': 'value',
                        'Average Cost
(USD)': 'cost',
                        'Total Shares
Held': 'quantity'
                    })
                    clean_df[["value", "cost", "quantity"]] = clean_df[["value", "cost", "quantity"]].astype(float)
                    total_value = clean_df["value"].sum()
                    invested = (clean_df["cost"] * clean_df["quantity"]).sum()
                    pnl = total_value - invested
                    pnl_pct = (pnl / invested) * 100 if invested else 0

                    st.info(f"**💰 Total Value:** ${total_value:,.2f}  |  **📈 P&L:** ${pnl:,.2f} ({pnl_pct:.2f}%)")
                except Exception:
                    st.warning("⚠️ Could not calculate P&L due to data format.")

            st.download_button("⬇️ Download CSV", clean_df.to_csv(index=False).encode("utf-8"),
                               "combined_portfolio.csv", "text/csv")

            excel = BytesIO()
            clean_df.to_excel(excel, index=False)
            st.download_button("⬇️ Download Excel", excel.getvalue(),
                               "combined_portfolio.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            pdf_file = generate_pdf(clean_df)
            st.download_button("⬇️ Download PDF", pdf_file,
                               "combined_portfolio.pdf", "application/pdf")

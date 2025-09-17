
import pandas as pd
import streamlit as st
from datetime import date

st.title("Seeking Alpha Portfolio CSV Generator")
st.write("Upload multiple Vested Holdings Excel files to generate a combined CSV for Seeking Alpha.")

uploaded_files = st.file_uploader("Upload Excel Files", type=["xlsx"], accept_multiple_files=True)
purchase_date = st.date_input("Select Purchase Date", date.today())

if uploaded_files:
    all_data = []

    for uploaded_file in uploaded_files:
        try:
            df = pd.read_excel(uploaded_file)
            df_clean = df[["Ticker", "Total Shares Held", "Average Cost (USD)"]].rename(columns={
                "Ticker": "symbol",
                "Total Shares Held": "quantity",
                "Average Cost (USD)": "cost"
            })
            all_data.append(df_clean)
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {e}")

    if all_data:
        combined_df = pd.concat(all_data)
        grouped_df = combined_df.groupby("symbol").apply(
            lambda x: pd.Series({
                "quantity": x["quantity"].sum(),
                "cost": (x["quantity"] * x["cost"]).sum() / x["quantity"].sum()
            })
        ).reset_index()

        grouped_df["date"] = purchase_date.strftime("%Y-%m-%d")
        final_df = grouped_df[["symbol", "quantity", "cost", "date"]]

        st.success("CSV ready! Download below.")
        st.download_button(
            label="Download CSV",
            data=final_df.to_csv(index=False).encode("utf-8"),
            file_name="Seeking_Alpha_Portfolio_Upload.csv",
            mime="text/csv"
        )

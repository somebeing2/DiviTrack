import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import time

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="DiviTrack | Dividend Auditor", layout="wide")

# --- 2. HELPER FUNCTIONS ---

@st.cache_data
def load_stock_map():
    """
    Fetches a master list of NSE stocks so users can search by name.
    Source: Open-source repository of NSE scripts.
    """
    try:
        # We use a lightweight CSV containing Symbol and Company Name
        url = "https://raw.githubusercontent.com/sfinias/NSE-Data/master/EQUITY_L.csv"
        df = pd.read_csv(url)
        
        # Create a combined column for the dropdown: "Reliance Industries (RELIANCE)"
        df['Search_Label'] = df['NAME OF COMPANY'] + " (" + df['SYMBOL'] + ")"
        return df
    except Exception as e:
        return pd.DataFrame() # Fallback if internet fails

# Load the list once
stock_map_df = load_stock_map()

# --- 3. DISCLAIMER & PRIVACY ---
st.warning("""
    ⚠️ **IMPORTANT DISCLAIMER:**
    * **Not Financial Advice:** This tool is for estimation only.
    * **Verify Data:** Dividend data is fetched from Yahoo Finance APIs. Verify with your Form 26AS.
    * **Tax Rules:** TDS calculations are estimates (10%) and do not account for specific exemptions.
""")

st.success("🔒 **Privacy Notice:** Your data is processed locally in RAM. It is never stored, saved, or shared. Refreshing this page wipes all data.")

# Initialize Session State
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# --- 4. SIDEBAR: SMART SEARCH INPUTS ---
st.sidebar.header("💰 Add to Portfolio")

with st.sidebar.form("add_stock_form"):
    
    # --- NEW: SEARCHABLE DROPDOWN ---
    if not stock_map_df.empty:
        # If we successfully loaded the list, show the dropdown
        selected_stock = st.selectbox(
            "Search Stock Name", 
            stock_map_df['Search_Label'],
            index=None,
            placeholder="Type to search (e.g. 'Tata Motors')"
        )
    else:
        # Fallback to text input if the list failed to load
        selected_stock = st.text_input("Stock Symbol (e.g., ITC.NS)", "ITC.NS")
    
    qty_input = st.number_input("Quantity", min_value=1, max_value=100000, value=100)
    buy_date_input = st.date_input("Purchase Date", date(2023, 1, 1))
    
    submitted = st.form_submit_button("Add Stock")
    
    if submitted:
        if selected_stock:
            # EXTRACT SYMBOL LOGIC
            # If came from dropdown, it looks like "Company (SYMBOL)"
            # We need to extract just "SYMBOL" and add ".NS"
            
            if "(" in selected_stock and ")" in selected_stock:
                # Extract text between parentheses
                clean_symbol = selected_stock.split("(")[-1].replace(")", "").strip()
                final_ticker = f"{clean_symbol}.NS"
            else:
                # Fallback for manual entry
                clean_symbol = selected_stock.upper().strip()
                final_ticker = clean_symbol if clean_symbol.endswith(".NS") else f"{clean_symbol}.NS"

            # Add to Session State
            st.session_state.portfolio.append({
                "Ticker": final_ticker,
                "Name": selected_stock.split("(")[0], # Store company name for display
                "Qty": qty_input,
                "BuyDate": buy_date_input
            })
            st.success(f"Added {final_ticker}")
        else:
            st.error("Please select a stock.")

# Clear Button
if st.sidebar.button("🗑️ Clear Portfolio"):
    st.session_state.portfolio = []
    st.rerun()

# --- 5. MAIN LOGIC ---
st.title("💸 DiviTrack: Dividend Tax & Eligibility Calculator")
st.markdown("This tool scans historical data to calculate your **Real In-Hand Profit** after TDS and Tax Slabs.")

# --- 6. TAX SETTINGS ---
st.subheader("⚙️ Tax Configuration")
col_tax1, col_tax2 = st.columns(2)
with col_tax1:
    tax_slab = st.selectbox("Select Your Income Tax Slab", [0, 10, 20, 30], index=3, format_func=lambda x: f"{x}% Slab")
with col_tax2:
    apply_tds = st.checkbox("Apply 10% TDS?", value=True, help="TDS is deducted if dividend > ₹5,000")

# --- 7. PROCESSING ENGINE ---
if len(st.session_state.portfolio) > 0:
    st.divider()
    
    total_gross_dividend = 0
    all_payouts = []

    progress_text = "Scanning secure data streams..."
    my_bar = st.progress(0, text=progress_text)
    
    total_stocks = len(st.session_state.portfolio)
    
    for i, item in enumerate(st.session_state.portfolio):
        ticker = item['Ticker']
        qty = item['Qty']
        buy_date = pd.to_datetime(item['BuyDate'])
        
        # Rate Limiting
        time.sleep(0.1) 
        my_bar.progress((i + 1) / total_stocks, text=f"Verifying {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            div_history = stock.dividends
            
            # CORE LOGIC
            my_dividends = div_history[div_history.index > buy_date]
            
            if not my_dividends.empty:
                for date_val, amount in my_dividends.items():
                    payout = amount * qty
                    total_gross_dividend += payout
                    
                    all_payouts.append({
                        "Stock": ticker,
                        "Ex-Date": date_val.date(),
                        "Dividend/Share": f"₹{amount}",
                        "Qty": qty,
                        "Total Payout": round(payout, 2)
                    })
            
        except Exception as e:
            st.error(f"Data Error for {ticker}. Check symbol.")

    my_bar.empty()

    # --- 8. RESULTS ---
    tds_amount = total_gross_dividend * 0.10 if apply_tds else 0
    income_tax_amount = total_gross_dividend * (tax_slab / 100)
    final_in_hand = total_gross_dividend - income_tax_amount

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dividend", f"₹{total_gross_dividend:,.2f}")
    m2.metric("Est. TDS (10%)", f"₹{tds_amount:,.2f}")
    m3.metric("Tax Liability", f"₹{income_tax_amount:,.2f}", f"{tax_slab}% Slab")
    m4.metric("Net Profit", f"₹{final_in_hand:,.2f}", delta="In Hand")

    # --- 9. EXPORT DATA ---
    st.subheader("📝 Transaction Log")
    if all_payouts:
        df_results = pd.DataFrame(all_payouts).sort_values(by="Ex-Date", ascending=False)
        st.dataframe(df_results, use_container_width=True)
        
        csv = df_results.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download for Tax Filing",
            data=csv,
            file_name='dividend_statement.csv',
            mime='text/csv',
        )
    else:
        st.info("No dividends found since purchase date.")

else:
    st.info("👈 Use the smart search in the sidebar to add stocks.")

# --- FOOTER ---
st.markdown("---")
st.markdown(
    "© 2026 | Built by **[Kevin Joseph](https://www.linkedin.com/in/kevin-joseph-in/)** | "
    "Powered by [Yahoo Finance](https://pypi.org/project/yfinance/) & [Streamlit](https://streamlit.io)"
)
st.caption("Disclaimer: This tool is for educational purposes and does not constitute financial advice.")

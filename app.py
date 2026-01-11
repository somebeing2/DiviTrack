import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import date
import time

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="DiviTrack | Dividend Auditor", layout="wide")

# --- 2. HELPER FUNCTIONS ---

@st.cache_data
def load_stock_map():
    """
    Reads the local 'EQUITY_L.csv' file to get the official list of NSE stocks.
    This ensures access to ALL ~1900+ companies (Small Cap, Mid Cap, etc.)
    without relying on external internet links.
    """
    try:
        # Read the file directly from the repo.
        # 'on_bad_lines' skips messy rows if the CSV is imperfect.
        df = pd.read_csv("EQUITY_L.csv", on_bad_lines='skip')
        
        # Standardize columns (remove extra spaces)
        df.columns = [c.strip() for c in df.columns]
        
        # Create a search label: "Wipro Ltd (WIPRO)"
        df['Search_Label'] = df['NAME OF COMPANY'] + " (" + df['SYMBOL'] + ")"
        return df
    except Exception:
        # Returns empty if file is missing or unreadable
        return pd.DataFrame()

# Load the data once
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

# --- 4. SIDEBAR: SMART INPUTS ---
st.sidebar.header("💰 Add to Portfolio")

with st.sidebar.form("add_stock_form"):
    
    # --- LOGIC: SEARCHABLE DROPDOWN ---
    selected_ticker_symbol = None
    selected_stock_name = None
    
    # Check if we successfully loaded the CSV list
    if not stock_map_df.empty:
        user_selection = st.selectbox(
            "Search Stock Name", 
            stock_map_df['Search_Label'],
            index=None,
            placeholder="Type 'Zomato' or 'Federal Bank'..."
        )
        
        if user_selection:
            # EXTRACT SYMBOL LOGIC
            # Format is: "The Federal Bank Ltd (FEDERALBNK)"
            # We split by '(' and take the last part.
            try:
                clean_symbol = user_selection.split("(")[-1].replace(")", "").strip()
                selected_ticker_symbol = f"{clean_symbol}.NS"
                selected_stock_name = user_selection.split("(")[0].strip()
            except:
                st.error("Error parsing stock name. Please use manual entry.")
            
    else:
        # FALLBACK: If CSV is missing, show manual text box
        st.error("⚠️ 'EQUITY_L.csv' not found. Please upload it to GitHub.")
        raw_input = st.text_input("Stock Symbol (Manual)", "ITC.NS")
        
        if raw_input:
            # Clean up manual input (remove spaces, uppercase)
            clean_symbol = raw_input.upper().replace(" ", "").strip()
            # Ensure it ends with .NS
            selected_ticker_symbol = clean_symbol if clean_symbol.endswith(".NS") else f"{clean_symbol}.NS"
            selected_stock_name = selected_ticker_symbol

    # Common Inputs
    qty_input = st.number_input("Quantity", min_value=1, max_value=100000, value=100)
    buy_date_input = st.date_input("Purchase Date", date(2023, 1, 1))
    
    submitted = st.form_submit_button("Add Stock")
    
    if submitted:
        if selected_ticker_symbol:
            st.session_state.portfolio.append({
                "Ticker": selected_ticker_symbol,
                "Name": selected_stock_name,
                "Qty": qty_input,
                "BuyDate": buy_date_input
            })
            st.success(f"Added {selected_stock_name}")
        else:
            st.error("Please select or enter a stock.")

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
    
    # --- ANTI-BLOCKING SESSION (CRITICAL FIX) ---
    # We create a fake browser session so Yahoo doesn't block us
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    for i, item in enumerate(st.session_state.portfolio):
        ticker = item['Ticker']
        name = item.get('Name', ticker) 
        qty = item['Qty']
        buy_date = pd.to_datetime(item['BuyDate'])
        
        # Rate Limiting
        time.sleep(0.1) 
        my_bar.progress((i + 1) / total_stocks, text=f"Verifying {name}...")
        
        try:
            # Pass the fake session to yfinance
            stock = yf.Ticker(ticker, session=session)
            div_history = stock.dividends
            
            # Check if data is empty (Fixes "Data Error" ambiguity)
            if div_history.empty:
                # Silent fail - just log nothing for this stock
                # or you could raise an error if you want to warn user
                pass
            else:
                # CORE LOGIC: Filter by Ex-Date
                my_dividends = div_history[div_history.index > buy_date]
                
                if not my_dividends.empty:
                    for date_val, amount in my_dividends.items():
                        payout = amount * qty
                        total_gross_dividend += payout
                        
                        all_payouts.append({
                            "Stock": name,
                            "Symbol": ticker,
                            "Ex-Date": date_val.date(),
                            "Dividend/Share": f"₹{amount}",
                            "Qty": qty,
                            "Total Payout": round(payout, 2)
                        })
            
        except Exception as e:
            # Specific error handling
            st.error(f"Could not fetch data for {name} ({ticker}). Server message: {e}")

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
    "© 2026 | Built by **[Kevin Joseph](https://www.linkedin.com/in/YOUR_LINKEDIN_ID_HERE)** | "
    "Powered by [Yahoo Finance](

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import re
import time

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="DiviTrack | Dividend Auditor", layout="wide")

# --- 2. SECURITY FUNCTIONS (NEW) ---
def validate_ticker(ticker):
    """
    Security Check: 
    1. specific length check to prevent buffer overflow attacks.
    2. Regex check to ensure only A-Z, 0-9, and dot (.) are allowed.
    """
    ticker = ticker.upper().strip()
    
    # Check 1: Length Limit (Indian tickers rarely exceed 15 chars)
    if len(ticker) > 20:
        return False, "Ticker symbol is too long."
    
    # Check 2: Allowed Characters (Alphanumeric + Dot only)
    # This prevents SQL Injection-style attacks or script injection
    if not re.match("^[A-Z0-9.]*$", ticker):
        return False, "Ticker contains invalid characters."
        
    return True, ticker

# --- 3. DISCLAIMER & PRIVACY (LEGAL CHECK) ---
st.warning("""
    ⚠️ **IMPORTANT DISCLAIMER:**
    * **Not Financial Advice:** This tool is for estimation only. Do not make investment decisions based solely on this data.
    * **Verify Data:** Dividend data is fetched from Yahoo Finance APIs and may be delayed. Verify with your Form 26AS.
    * **Tax Rules:** TDS calculations are estimates (10%) and do not account for specific exemptions (Form 15G/H).
""")

st.success("🔒 **Privacy Notice:** Your data is processed locally in RAM. It is never stored, saved, or shared. Refreshing this page wipes all data.")

# Initialize Session State
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# --- 4. SIDEBAR: SECURE INPUTS ---
st.sidebar.header("💰 Add to Portfolio")

with st.sidebar.form("add_stock_form"):
    # Input
    raw_ticker = st.text_input("Stock Symbol (e.g., ITC.NS)", "ITC.NS")
    qty_input = st.number_input("Quantity", min_value=1, max_value=100000, value=100) # Added max_value for safety
    buy_date_input = st.date_input("Purchase Date", date(2023, 1, 1))
    
    submitted = st.form_submit_button("Add Stock")
    
    if submitted:
        # --- SECURITY CHECK ---
        is_valid, clean_ticker = validate_ticker(raw_ticker)
        
        if is_valid:
            # Indian Market Context Helper
            if not clean_ticker.endswith(".NS") and not clean_ticker.endswith(".BO") and not clean_ticker.isalpha():
                 st.sidebar.warning("Tip: For India, usually add .NS (e.g., RELIANCE.NS)")
            
            # Add to Session State
            st.session_state.portfolio.append({
                "Ticker": clean_ticker,
                "Qty": qty_input,
                "BuyDate": buy_date_input
            })
            st.success(f"Securely added {clean_ticker}")
        else:
            # If validation fails, show error
            st.error(f"Security Alert: {clean_ticker}")

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

    # Progress bar for UX
    progress_text = "Scanning secure data streams..."
    my_bar = st.progress(0, text=progress_text)
    
    total_stocks = len(st.session_state.portfolio)
    
    for i, item in enumerate(st.session_state.portfolio):
        ticker = item['Ticker']
        qty = item['Qty']
        buy_date = pd.to_datetime(item['BuyDate'])
        
        # Rate Limiting Simulation (Prevents API spamming)
        time.sleep(0.1) 
        my_bar.progress((i + 1) / total_stocks, text=f"Verifying {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            div_history = stock.dividends
            
            # CORE LOGIC: Filter by Ex-Date
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
    # Tax Math
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
    st.info("👈 Add stocks securely from the sidebar.")
# --- FOOTER ---
st.markdown("---")

st.markdown(
    "© 2026 | Built by **[Kevin Joseph](https://www.linkedin.com/in/kevin-joseph-in/)** | "
    "Powered by [Yahoo Finance](https://pypi.org/project/yfinance/) & [Streamlit](https://streamlit.io)")

st.caption("Disclaimer: This tool is for educational purposes and does not constitute financial advice. Always verify with official documents.")
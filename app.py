import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="KP Brothers", page_icon="🚛", layout="wide")

# --- 2. GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def get_gspread_client():
    """Authenticates with Google using the secrets file."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(credentials)

def get_worksheet():
    """Connects to the specific Google Sheet URL."""
    gc = get_gspread_client()
    sheet = gc.open_by_url(st.secrets["google_sheets"]["url"])
    return sheet.sheet1

# --- 3. DATA HANDLING FUNCTIONS (CLOUD) ---
def load_data():
    """Loads and formats data directly from the Google Sheet."""
    expected_columns = [
        "Date", "Client Name", "Vehicle Type", "Vehicle ID", "Driver Name",
        "Rate", "Qty/Hours", "Total Revenue", "Amount Received", "Client Balance Due",
        "Diesel Total", "Diesel Paid (Cash)", "Diesel Credit",
        "Basic Pay", "Overtime Hours", "Overtime Rate", "Wages Total", "Wages Paid (Cash)", "Wages Credit",
        "Oil Change Cost", "Tyre Cost", "Tyre Details", "Grease Cost", "Workshop Cost", "Workshop Comment",
        "Total Expense", "Total Expense Paid", "Total Expense Credit"
    ]
    
    worksheet = get_worksheet()
    records = worksheet.get_all_records()
    
    if not records:
        # If the sheet is completely blank, build the headers automatically
        worksheet.append_row(expected_columns)
        return pd.DataFrame(columns=expected_columns)
        
    df = pd.DataFrame(records)
    
    # Format Date
    if not df.empty and "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
        df = df.dropna(subset=['Date'])
        
    # Ensure all expected columns exist to prevent crashes
    for col in expected_columns:
        if col not in df.columns:
            if col == "Overtime Rate":
                df[col] = 200.0
            elif "Tyre Details" in col or "Workshop Comment" in col:
                df[col] = "None"
            else:
                df[col] = 0.0
                
    df = df[expected_columns]
    return df

def save_entry(entry_date, client, v_type, v_id, driver, 
               rate, qty, received, 
               diesel_tot, diesel_paid, 
               basic_pay, overtime_hours, overtime_rate, wages_paid,
               oil_change, tyre_cost, tyre_details, grease, workshop_cost, workshop_comment):
    """Calculates balances and appends a single new row to Google Sheets."""
    
    total_rev = rate * qty
    client_balance = total_rev - received
    
    wages_tot = basic_pay + (overtime_hours * overtime_rate)
    
    diesel_credit = diesel_tot - diesel_paid
    wages_credit = wages_tot - wages_paid
    
    total_repair_cash = oil_change + tyre_cost + grease + workshop_cost
    
    total_expense = diesel_tot + wages_tot + total_repair_cash
    total_expense_paid = diesel_paid + wages_paid + total_repair_cash
    total_expense_credit = diesel_credit + wages_credit
    
    new_row = [
        str(entry_date), client.title(), v_type, v_id.upper(), driver.title(),
        float(rate), float(qty), float(total_rev), float(received), float(client_balance),
        float(diesel_tot), float(diesel_paid), float(diesel_credit),
        float(basic_pay), float(overtime_hours), float(overtime_rate), float(wages_tot), float(wages_paid), float(wages_credit),
        float(oil_change), float(tyre_cost), tyre_details, float(grease), float(workshop_cost), workshop_comment.title(),
        float(total_expense), float(total_expense_paid), float(total_expense_credit)
    ]
    
    worksheet = get_worksheet()
    worksheet.append_row(new_row)

def overwrite_data(edited_df):
    """Overwrites the entire Google Sheet when saving edits/deletions."""
    worksheet = get_worksheet()
    worksheet.clear()
    
    edited_df["Date"] = edited_df["Date"].astype(str)
    
    data_matrix = [edited_df.columns.values.tolist()] + edited_df.values.tolist()
    worksheet.update(data_matrix)

# --- 4. LOAD DATA EARLY TO BUILD DROPDOWNS ---
df = load_data()

if not df.empty:
    saved_clients = ["-- Select --"] + sorted(df["Client Name"].unique().tolist())
    saved_vids = ["-- Select --"] + sorted(df["Vehicle ID"].unique().tolist())
    saved_drivers = ["-- Select --"] + sorted(df["Driver Name"].unique().tolist())
else:
    saved_clients = ["-- Select --"]
    saved_vids = ["-- Select --"]
    saved_drivers = ["-- Select --"]

# --- 5. SIDEBAR CONTROLS ---
st.sidebar.title("🚛 Controls")
tab_log, tab_filter = st.sidebar.tabs(["Log Entry", "Filters"])

with tab_log:
    st.header("New Entry")
    
    st.markdown("**Date & Vehicle Type**")
    col_date, col_type = st.columns(2)
    entry_date = col_date.date_input("Entry Date", datetime.today())
    v_type = col_type.selectbox("Vehicle Type", ["Lorry", "JCB", "Car"])
    
    st.divider()
    
    st.markdown("**Client Information**")
    c_col1, c_col2 = st.columns(2)
    sel_client = c_col1.selectbox("Select Saved Client", saved_clients)
    new_client = c_col2.text_input("OR Enter New Client")
    
    st.markdown("**Vehicle Information**")
    v_col1, v_col2 = st.columns(2)
    sel_vid = v_col1.selectbox("Select Saved Vehicle ID", saved_vids)
    new_vid = v_col2.text_input("OR Enter New Vehicle ID")
    
    st.markdown("**Driver Information**")
    d_col1, d_col2 = st.columns(2)
    sel_driver = d_col1.selectbox("Select Saved Driver", saved_drivers)
    new_driver = d_col2.text_input("OR Enter New Driver")
    
    st.divider()
    
    st.markdown("**Revenue Details**")
    rate = st.number_input("Rate (₹)", min_value=0.0, step=50.0, format="%.2f")
    qty = st.number_input("Qty/Hours/Trips", min_value=0.0, step=0.5, format="%.1f")
    
    total_rev_calc = rate * qty
    if total_rev_calc > 0:
        st.success(f"**Calculated Revenue:** ₹ {total_rev_calc:,.2f}")
        
    amount_received = st.number_input("Amount Received from Client (₹)", min_value=0.0, step=100.0, format="%.2f")
    
    st.divider()
    
    st.markdown("**Daily Operations Expense**")
    e_col1, e_col2 = st.columns(2)
    diesel_tot = e_col1.number_input("Total Diesel Bill (₹)", min_value=0.0, step=100.0)
    diesel_paid = e_col2.number_input("Diesel Paid Cash (₹)", min_value=0.0, step=100.0)
    
    st.markdown("**Driver Wages**")
    w_col1, w_col2, w_col3 = st.columns(3)
    basic_pay = w_col1.number_input("Basic Pay (₹)", min_value=0.0, step=50.0)
    overtime_hours = w_col2.number_input("Overtime (Hrs)", min_value=0.0, step=0.5)
    overtime_rate = w_col3.number_input("OT Rate (₹/Hr)", min_value=0.0, value=200.0, step=50.0)
    
    wages_tot_calc = basic_pay + (overtime_hours * overtime_rate)
    if wages_tot_calc > 0:
        st.success(f"**Total Wages:** ₹ {wages_tot_calc:,.2f} *(Basic: ₹{basic_pay} + OT: ₹{overtime_hours * overtime_rate})*")
        
    wages_paid = st.number_input("Wages Paid Cash (₹)", min_value=0.0, step=50.0)
    
    with st.expander("🛠️ Maintenance & Repairs (Cash Paid)"):
        oil_change = st.number_input("Oil Change (₹)", min_value=0.0, step=100.0)
        st.divider()
        tyre_cost = st.number_input("Tyre Cost (₹)", min_value=0.0, step=500.0)
        tyre_details = st.selectbox("Tyre Position/Type", ["None", "New - Front", "New - Back", "Used - Front", "Used - Back", "Puncture Repair"])
        st.divider()
        grease = st.number_input("Grease (₹)", min_value=0.0, step=50.0)
        st.divider()
        workshop_cost = st.number_input("Workshop Cost (₹)", min_value=0.0, step=100.0)
        workshop_comment = st.text_input("Workshop Comment (Which part/where?)")
    
    if st.button("Save Record", type="primary"):
        final_client = new_client.strip() if new_client.strip() else (sel_client if sel_client != "-- Select --" else "")
        final_vid = new_vid.strip() if new_vid.strip() else (sel_vid if sel_vid != "-- Select --" else "")
        final_driver = new_driver.strip() if new_driver.strip() else (sel_driver if sel_driver != "-- Select --" else "")
        
        if not final_client or not final_vid or not final_driver:
            st.error("⚠️ Please ensure Client Name, Vehicle ID, and Driver Name are provided.")
        else:
            with st.spinner("Saving to Google Sheets..."):
                save_entry(entry_date, final_client, v_type, final_vid, final_driver, 
                           rate, qty, amount_received, 
                           diesel_tot, diesel_paid, 
                           basic_pay, overtime_hours, overtime_rate, wages_paid,
                           oil_change, tyre_cost, tyre_details, grease, workshop_cost, workshop_comment)
            st.success(f"Saved {final_vid.upper()} successfully! Note: Clear your inputs manually for the next entry.")

# Reload data after potential save to update main dashboard
df = load_data()

# --- 6. APPLY FILTERS ---
with tab_filter:
    st.header("Dashboard Filters")
    if not df.empty:
        type_list = sorted(df['Vehicle Type'].unique().tolist())
        selected_types = st.multiselect("Vehicle Type", type_list, default=type_list)
        
        client_list = sorted(df['Client Name'].unique().tolist())
        selected_clients = st.multiselect("Client", client_list, default=client_list)
        
        driver_list = sorted(df['Driver Name'].unique().tolist())
        selected_drivers = st.multiselect("Driver Name", driver_list, default=driver_list)
        
        filter_type = st.radio("Time Period", ["All Time", "Single Date", "Date Range (Period)"])
        
        if filter_type == "Single Date":
            selected_date = st.date_input("Select Date", datetime.today())
        elif filter_type == "Date Range (Period)":
            date_range = st.date_input("Select Date Range", [datetime.today() - timedelta(days=7), datetime.today()])

if df.empty:
    st.info("No data available. Add a record in the sidebar.")
else:
    filtered_df = df[
        (df['Vehicle Type'].isin(selected_types)) &
        (df['Client Name'].isin(selected_clients)) &
        (df['Driver Name'].isin(selected_drivers))
    ]
    
    if filter_type == "Single Date":
        filtered_df = filtered_df[filtered_df['Date'] == selected_date]
    elif filter_type == "Date Range (Period)" and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df['Date'] >= start_date) & (filtered_df['Date'] <= end_date)]

    # --- 7. MAIN DASHBOARD ---
  
st.title("KP_Brothers")
tab_dash, tab_edit = st.tabs(["📊 Main Dashboard", "✏️ Edit / Delete Records"])

# --- DASHBOARD TAB ---
with tab_dash:
    if df.empty:
        st.info("No data available. Add a record in the sidebar.")
    else:
        if filtered_df.empty:
            st.warning("No data matches your selected filters.")
        else:
            st.subheader("Financial Overview (Filtered Data)")
            
            t_rev = filtered_df['Total Revenue'].sum()
            t_received = filtered_df['Amount Received'].sum()
            t_client_bal = filtered_df['Client Balance Due'].sum()
            
            t_exp = filtered_df['Total Expense'].sum()
            t_exp_paid = filtered_df['Total Expense Paid'].sum()
            t_exp_credit = filtered_df['Total Expense Credit'].sum()
            
            net_profit = t_rev - t_exp
            cash_in_hand = t_received - t_exp_paid
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Net Profit (Book Value)", f"₹ {net_profit:,.2f}")
            m2.metric("Total Revenue", f"₹ {t_rev:,.2f}")
            m3.metric("Total Expenses", f"₹ {t_exp:,.2f}")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Cash In Hand (Actual)", f"₹ {cash_in_hand:,.2f}")
            c2.metric("Market Outstanding (Customers Owe)", f"₹ {t_client_bal:,.2f}")
            c3.metric("Pending Payables (You Owe)", f"₹ {t_exp_credit:,.2f}")
            
            st.divider()

            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("👥 Customer Credit Tracker")
                client_credit_df = filtered_df.groupby("Client Name")[["Total Revenue", "Amount Received", "Client Balance Due"]].sum().reset_index()
                client_credit_df = client_credit_df[client_credit_df["Client Balance Due"] > 0].sort_values("Client Balance Due", ascending=False)
                
                if client_credit_df.empty:
                    st.success("All selected clients have paid in full!")
                else:
                    st.dataframe(client_credit_df, use_container_width=True, hide_index=True)

            with col_right:
                st.subheader("⛽ Expense Payable Tracker")
                exp_credit_df = filtered_df.groupby("Vehicle Type")[["Diesel Credit", "Wages Credit", "Total Expense Credit"]].sum().reset_index()
                exp_credit_df = exp_credit_df[exp_credit_df["Total Expense Credit"] > 0].sort_values("Total Expense Credit", ascending=False)
                
                if exp_credit_df.empty:
                    st.success("All selected expenses have been paid in cash!")
                else:
                    st.dataframe(exp_credit_df, use_container_width=True, hide_index=True)

            st.divider()

            st.subheader("Detailed Master Log")
            
            display_df = filtered_df.sort_values(by="Date", ascending=False).copy()
            
            if not display_df.empty:
                cols_to_sum = [
                    "Qty/Hours", "Total Revenue", "Amount Received", "Client Balance Due",
                    "Diesel Total", "Diesel Paid (Cash)", "Diesel Credit",
                    "Basic Pay", "Overtime Hours", "Wages Total", "Wages Paid (Cash)", "Wages Credit",
                    "Oil Change Cost", "Tyre Cost", "Grease Cost", "Workshop Cost",
                    "Total Expense", "Total Expense Paid", "Total Expense Credit"
                ]
                
                totals = {col: display_df[col].sum() for col in cols_to_sum}
                totals["Date"] = "TOTAL" 
                
                total_row = pd.DataFrame([totals])
                display_df = pd.concat([display_df, total_row], ignore_index=True)
                
                display_df = display_df.fillna("")
                display_df["Date"] = display_df["Date"].astype(str)

            st.dataframe(display_df, use_container_width=True, hide_index=True)

# --- NEW EDIT TAB (CLOUD SAVING) ---
with tab_edit:
    st.subheader("✏️ Edit Historical Database")
    
    if not df.empty:
        # data_editor allows seamless editing of the dataframe on the screen
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 Save Changes to Google Sheets", type="primary"):
            with st.spinner("Syncing edits to the cloud..."):
                try:
                    overwrite_data(edited_df)
                    st.success("Changes saved to Google Sheets! Please refresh the browser to update the Dashboard charts.")
                except Exception as e:
                    st.error(f"Error saving data: {e}")
    else:
        st.info("Your database is currently empty.")
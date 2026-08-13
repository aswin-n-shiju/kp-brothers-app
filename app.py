import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION & CUSTOM CSS ---
st.set_page_config(
    page_title="KP_Brothers - Fleet Operations", 
    page_icon="🚛", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Client Polish
st.markdown("""
<style>
    /* Global background and font styling */
    .main {
        background-color: #f8f9fa;
    }
    /* Card headers */
    .stHeader {
        color: #1E3A8A;
    }
    /* Metric Card Styling */
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700;
        color: #1E3A8A;
    }
    /* Custom button polish */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# --- 2. SECURITY: LOGIN SCREEN ---
def check_password():
    """Returns `True` if the user has the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"] 
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 KP_Brothers Portal")
        st.subheader("Restricted Access")
        st.text_input("Please enter the master password:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 KP_Brothers Portal")
        st.subheader("Restricted Access")
        st.text_input("Please enter the master password:", type="password", on_change=password_entered, key="password")
        st.error("🚫 Incorrect password. Please try again.")
        return False
    else:
        return True

if not check_password():
    st.stop() 


# --- 3. GOOGLE SHEETS CONNECTION ---
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
    sheet = gc.open_by_url(st.secrets["google_sheets"]["https://docs.google.com/spreadsheets/d/1PvUMKvR3W2r2jOJhCuagxPtPVGye2PtVfKKP-vzVPVY/edit?gid=0#gid=0"])
    return sheet.sheet1


# --- 4. DATA HANDLING FUNCTIONS (WITH CACHING FOR SPEED) ---
@st.cache_data(ttl=120)  # Caches data for 2 mins to dramatically speed up app
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
    
    try:
        worksheet = get_worksheet()
        records = worksheet.get_all_records()
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return pd.DataFrame(columns=expected_columns)
    
    if not records:
        worksheet.append_row(expected_columns)
        return pd.DataFrame(columns=expected_columns)
        
    df = pd.DataFrame(records)
    
    if not df.empty and "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
        df = df.dropna(subset=['Date'])
        
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
    """Calculates balances and appends a new row to Google Sheets."""
    
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
    st.cache_data.clear()  # Clear cache so new entry shows immediately

def overwrite_data(edited_df):
    """Overwrites the entire Google Sheet when saving edits/deletions."""
    worksheet = get_worksheet()
    worksheet.clear()
    
    edited_df["Date"] = edited_df["Date"].astype(str)
    
    data_matrix = [edited_df.columns.values.tolist()] + edited_df.values.tolist()
    worksheet.update(data_matrix)
    st.cache_data.clear()  # Clear cache after sync


# --- 5. LOAD INITIAL DATA ---
df = load_data()

if not df.empty:
    saved_clients = ["-- Select --"] + sorted(df["Client Name"].unique().tolist())
    saved_vids = ["-- Select --"] + sorted(df["Vehicle ID"].unique().tolist())
    saved_drivers = ["-- Select --"] + sorted(df["Driver Name"].unique().tolist())
else:
    saved_clients = ["-- Select --"]
    saved_vids = ["-- Select --"]
    saved_drivers = ["-- Select --"]


# --- 6. SIDEBAR CONTROLS ---
st.sidebar.image("https://img.icons8.com/color/96/dump-truck.png", width=64)
st.sidebar.title("KP_Brothers")
st.sidebar.caption("Fleet Management System")

tab_log, tab_filter = st.sidebar.tabs(["📝 Log Entry", "🔍 Filters"])

with tab_log:
    st.subheader("New Operations Entry")
    
    with st.container(border=True):
        st.markdown("##### 📅 Date & Vehicle")
        col_date, col_type = st.columns(2)
        entry_date = col_date.date_input("Date", datetime.today())
        v_type = col_type.selectbox("Vehicle Type", ["Lorry", "JCB", "Car"])
    
    with st.container(border=True):
        st.markdown("##### 👤 Client Details")
        sel_client = st.selectbox("Select Saved Client", saved_clients)
        new_client = st.text_input("OR New Client Name")
    
    with st.container(border=True):
        st.markdown("##### 🚜 Vehicle & Driver")
        v_col1, v_col2 = st.columns(2)
        sel_vid = v_col1.selectbox("Vehicle ID", saved_vids)
        new_vid = v_col2.text_input("OR New ID")
        
        d_col1, d_col2 = st.columns(2)
        sel_driver = d_col1.selectbox("Driver Name", saved_drivers)
        new_driver = d_col2.text_input("OR New Driver")
    
    with st.container(border=True):
        st.markdown("##### 💰 Revenue Details")
        col_r1, col_r2 = st.columns(2)
        rate = col_r1.number_input("Rate (₹)", min_value=0.0, step=50.0, format="%.2f")
        qty = col_r2.number_input("Qty / Hours", min_value=0.0, step=0.5, format="%.1f")
        
        total_rev_calc = rate * qty
        if total_rev_calc > 0:
            st.info(f"**Total Bill:** ₹ {total_rev_calc:,.2f}")
            
        amount_received = st.number_input("Amount Received (₹)", min_value=0.0, step=100.0, format="%.2f")
    
    with st.container(border=True):
        st.markdown("##### ⛽ Daily Operating Expenses")
        e_col1, e_col2 = st.columns(2)
        diesel_tot = e_col1.number_input("Diesel Bill (₹)", min_value=0.0, step=100.0)
        diesel_paid = e_col2.number_input("Diesel Paid Cash (₹)", min_value=0.0, step=100.0)
        
        st.markdown("---")
        st.markdown("**Driver Wages**")
        w_col1, w_col2 = st.columns(2)
        basic_pay = w_col1.number_input("Basic Pay (₹)", min_value=0.0, step=50.0)
        overtime_hours = w_col2.number_input("Overtime (Hrs)", min_value=0.0, step=0.5)
        overtime_rate = st.number_input("OT Rate (₹/Hr)", min_value=0.0, value=200.0, step=50.0)
        
        wages_tot_calc = basic_pay + (overtime_hours * overtime_rate)
        if wages_tot_calc > 0:
            st.info(f"**Total Wage:** ₹ {wages_tot_calc:,.2f}")
            
        wages_paid = st.number_input("Wages Paid Cash (₹)", min_value=0.0, step=50.0)
    
    with st.expander("🛠️ Maintenance & Repairs (Cash Paid)"):
        oil_change = st.number_input("Oil Change (₹)", min_value=0.0, step=100.0)
        tyre_cost = st.number_input("Tyre Cost (₹)", min_value=0.0, step=500.0)
        tyre_details = st.selectbox("Tyre Position", ["None", "New - Front", "New - Back", "Used - Front", "Used - Back", "Puncture Repair"])
        grease = st.number_input("Grease (₹)", min_value=0.0, step=50.0)
        workshop_cost = st.number_input("Workshop Cost (₹)", min_value=0.0, step=100.0)
        workshop_comment = st.text_input("Workshop Remarks")
    
    if st.button("💾 Save Entry to Cloud", type="primary", use_container_width=True):
        final_client = new_client.strip() if new_client.strip() else (sel_client if sel_client != "-- Select --" else "")
        final_vid = new_vid.strip() if new_vid.strip() else (sel_vid if sel_vid != "-- Select --" else "")
        final_driver = new_driver.strip() if new_driver.strip() else (sel_driver if sel_driver != "-- Select --" else "")
        
        if not final_client or not final_vid or not final_driver:
            st.error("⚠️ Client, Vehicle ID, and Driver Name are required.")
        else:
            with st.spinner("Syncing to Google Sheets..."):
                save_entry(entry_date, final_client, v_type, final_vid, final_driver, 
                           rate, qty, amount_received, 
                           diesel_tot, diesel_paid, 
                           basic_pay, overtime_hours, overtime_rate, wages_paid,
                           oil_change, tyre_cost, tyre_details, grease, workshop_cost, workshop_comment)
            st.success(f"✅ Record saved for {final_vid.upper()}!")
            st.rerun()

# --- 7. APPLY FILTERS ---
with tab_filter:
    st.subheader("Filter Dashboard")
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
            date_range = st.date_input("Select Date Range", [datetime.today() - timedelta(days=30), datetime.today()])


# --- 8. MAIN DASHBOARD UI ---
st.title("🚛 KP_Brothers Operations Dashboard")

tab_dash, tab_analytics, tab_edit = st.tabs(["📊 Financial Overview", "📈 Analytics & Charts", "✏️ Edit / Delete Database"])

# --- TAB 1: FINANCIAL OVERVIEW ---
with tab_dash:
    if df.empty:
        st.info("No data available in Google Sheets. Add a record in the sidebar to get started.")
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

        if filtered_df.empty:
            st.warning("No records match your selected filters.")
        else:
            # Top Executive Metrics in Bordered Cards
            with st.container(border=True):
                st.markdown("#### 💵 Key Financial Performance")
                
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
                m2.metric("Total Revenue Generated", f"₹ {t_rev:,.2f}")
                m3.metric("Total Operations Expense", f"₹ {t_exp:,.2f}")
                
                st.divider()
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Cash In Hand (Collected)", f"₹ {cash_in_hand:,.2f}")
                c2.metric("Market Outstanding (Uncollected)", f"₹ {t_client_bal:,.2f}", delta_color="inverse")
                c3.metric("Pending Payables (You Owe)", f"₹ {t_exp_credit:,.2f}", delta_color="inverse")

            st.write(" ")

            # Balances & Credit Trackers
            col_left, col_right = st.columns(2)
            
            with col_left:
                with st.container(border=True):
                    st.markdown("#### 👥 Customer Outstanding Balances")
                    client_credit_df = filtered_df.groupby("Client Name")[["Total Revenue", "Amount Received", "Client Balance Due"]].sum().reset_index()
                    client_credit_df = client_credit_df[client_credit_df["Client Balance Due"] > 0].sort_values("Client Balance Due", ascending=False)
                    
                    if client_credit_df.empty:
                        st.success("✅ All selected clients have settled their balances!")
                    else:
                        st.dataframe(client_credit_df, use_container_width=True, hide_index=True)

            with col_right:
                with st.container(border=True):
                    st.markdown("#### ⛽ Pending Expense Payables")
                    exp_credit_df = filtered_df.groupby("Vehicle Type")[["Diesel Credit", "Wages Credit", "Total Expense Credit"]].sum().reset_index()
                    exp_credit_df = exp_credit_df[exp_credit_df["Total Expense Credit"] > 0].sort_values("Total Expense Credit", ascending=False)
                    
                    if exp_credit_df.empty:
                        st.success("✅ All operating expenses have been fully paid in cash!")
                    else:
                        st.dataframe(exp_credit_df, use_container_width=True, hide_index=True)

            st.write(" ")

            # Detailed Master Table
            with st.container(border=True):
                col_tbl_hdr, col_btn = st.columns([4, 1])
                col_tbl_hdr.markdown("#### 📋 Detailed Operations Log")
                
                # Export to CSV feature for client convenience
                csv_data = filtered_df.to_csv(index=False).encode('utf-8')
                col_btn.download_button(
                    label="📥 Export Report (CSV)",
                    data=csv_data,
                    file_name=f"KP_Brothers_Report_{datetime.today().strftime('%Y_%m_%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
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


# --- TAB 2: VISUAL ANALYTICS & CHARTS ---
with tab_analytics:
    if df.empty or filtered_df.empty:
        st.info("No data available to plot charts.")
    else:
        st.subheader("📈 Visual Fleet Analytics")
        
        ch_col1, ch_col2 = st.columns(2)
        
        with ch_col1:
            with st.container(border=True):
                st.markdown("##### Revenue vs. Expense by Vehicle Type")
                v_summary = filtered_df.groupby("Vehicle Type")[["Total Revenue", "Total Expense"]].sum()
                st.bar_chart(v_summary, height=300)
                
        with ch_col2:
            with st.container(border=True):
                st.markdown("##### Expense Category Breakdown (₹)")
                exp_breakdown = pd.DataFrame({
                    "Category": ["Diesel", "Wages", "Oil Change", "Tyres", "Grease", "Workshop"],
                    "Amount": [
                        filtered_df["Diesel Total"].sum(),
                        filtered_df["Wages Total"].sum(),
                        filtered_df["Oil Change Cost"].sum(),
                        filtered_df["Tyre Cost"].sum(),
                        filtered_df["Grease Cost"].sum(),
                        filtered_df["Workshop Cost"].sum()
                    ]
                }).set_index("Category")
                st.bar_chart(exp_breakdown, height=300)


# --- TAB 3: EDIT DATABASE ---
with tab_edit:
    st.subheader("✏️ Edit Live Google Sheet Records")
    st.caption("Double-click any cell to edit text/numbers, or check the box on the far left and press 'Delete' on your keyboard to remove a row.")
    
    if not df.empty:
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 Sync Edits to Google Sheets", type="primary"):
            with st.spinner("Updating Google Cloud Database..."):
                try:
                    overwrite_data(edited_df)
                    st.success("✅ Changes successfully synced to Google Sheets!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving data: {e}")
    else:
        st.info("Your database is currently empty.")
import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="JCB Tracker", page_icon="🚜", layout="wide")
# Updated to the new file name
CSV_FILE = "jcb_data.csv"

# --- 2. DATA HANDLING FUNCTIONS ---
def load_data():
    """Loads and safely formats the data from the CSV file."""
    expected_columns = [
        "Timestamp", "Vehicle ID", "Driver Name", "Unit Rate", 
        "Working Hour", "Rate", "Diesel", "Wages", "Repair", "Expense"
    ]
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=expected_columns)
        df.to_csv(CSV_FILE, index=False)
        return df
    else:
        df = pd.read_csv(CSV_FILE)
        if not df.empty and "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors='coerce')
            df = df.dropna(subset=['Timestamp'])
            df['Date Only'] = df['Timestamp'].dt.date
            
            if "Driver Name" not in df.columns:
                df["Driver Name"] = "Unknown"
        return df

def save_entry(vehicle_id, driver_name, unit_rate, working_hour, diesel, wages, repair):
    """Calculates totals and saves the new row to the CSV."""
    now = datetime.now()
    
    total_rate = unit_rate * working_hour
    total_expense = diesel + wages + repair
    
    new_row = pd.DataFrame([{
        "Timestamp": now,
        "Vehicle ID": vehicle_id.upper(),
        "Driver Name": driver_name.title(),
        "Unit Rate": float(unit_rate),
        "Working Hour": float(working_hour),
        "Rate": float(total_rate),
        "Diesel": float(diesel),
        "Wages": float(wages),
        "Repair": float(repair),
        "Expense": float(total_expense)
    }])
    new_row.to_csv(CSV_FILE, mode='a', header=not os.path.exists(CSV_FILE), index=False)

# --- 3. SIDEBAR CONTROLS ---
st.sidebar.title("🚜 Controls")
tab_log, tab_filter = st.sidebar.tabs(["Log Entry", "Filters"])

with tab_log:
    st.header("New Entry")
    with st.form("entry_form", clear_on_submit=True):
        st.markdown("**Basic Details**")
        vehicle_input = st.text_input("Vehicle ID (e.g., JCB-01)")
        driver_input = st.text_input("Driver Name")
        
        st.markdown("**Revenue Details**")
        unit_rate = st.number_input("Unit Rate (₹/Hr)", min_value=0.0, step=50.0, format="%.2f")
        working_hour = st.number_input("Working Hours", min_value=0.0, step=0.5, format="%.1f")
        
        st.markdown("**Expense Details**")
        diesel = st.number_input("Diesel Cost (₹)", min_value=0.0, step=100.0, format="%.2f")
        wages = st.number_input("Wages (₹)", min_value=0.0, step=50.0, format="%.2f")
        repair = st.number_input("Repair/Other (₹)", min_value=0.0, step=50.0, format="%.2f")
        
        submitted = st.form_submit_button("Save Record")
        if submitted:
            if vehicle_input.strip() == "":
                st.error("Please enter a Vehicle ID.")
            elif driver_input.strip() == "":
                st.error("Please enter the Driver's Name.")
            else:
                save_entry(vehicle_input, driver_input, unit_rate, working_hour, diesel, wages, repair)
                st.success(f"Saved {vehicle_input.upper()} successfully!")

df = load_data()

# --- 4. APPLY FILTERS ---
with tab_filter:
    st.header("Dashboard Filters")
    if not df.empty:
        vehicle_list = sorted(df['Vehicle ID'].unique().tolist())
        selected_vehicles = st.multiselect("Select Vehicle(s)", vehicle_list, default=vehicle_list)
        
        driver_list = sorted(df['Driver Name'].unique().tolist())
        selected_drivers = st.multiselect("Select Driver(s)", driver_list, default=driver_list)
        
        filter_type = st.radio("Time Period", ["All Time", "Single Date", "Date Range (Period)"])
        
        if filter_type == "Single Date":
            selected_date = st.date_input("Select Date", datetime.today())
        elif filter_type == "Date Range (Period)":
            date_range = st.date_input("Select Date Range", [datetime.today() - timedelta(days=7), datetime.today()])

if df.empty:
    st.info("No data available. Add a record in the sidebar.")
else:
    filtered_df = df[
        (df['Vehicle ID'].isin(selected_vehicles)) &
        (df['Driver Name'].isin(selected_drivers))
    ]
    
    if filter_type == "Single Date":
        filtered_df = filtered_df[filtered_df['Date Only'] == selected_date]
    elif filter_type == "Date Range (Period)" and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df['Date Only'] >= start_date) & (filtered_df['Date Only'] <= end_date)]

    # --- 5. MAIN DASHBOARD ---
    st.title("🚜 JCB Operations Tracker")
    
    if filtered_df.empty:
        st.warning("No data matches your selected filters.")
    else:
        total_revenue = filtered_df['Rate'].sum()
        total_expenses = filtered_df['Expense'].sum()
        net_profit = total_revenue - total_expenses
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Revenue", f"₹ {total_revenue:,.2f}")
        col2.metric("Total Expenses", f"₹ {total_expenses:,.2f}")
        profit_color = "normal" if net_profit >= 0 else "inverse"
        col3.metric("Net Profit", f"₹ {net_profit:,.2f}", delta=f"₹ {net_profit:,.2f}", delta_color=profit_color)
        
        st.divider()

        st.subheader("Revenue vs. Expenses Trend")
        chart_data = filtered_df.groupby('Date Only')[['Rate', 'Expense']].sum()
        st.bar_chart(chart_data, color=["#2e7b32", "#d32f2f"]) 
        
        st.divider()

        st.subheader("Daily Profit Summary")
        daily_summary = filtered_df.groupby('Date Only')[['Rate', 'Expense']].sum().reset_index()
        daily_summary['Total Profit'] = daily_summary['Rate'] - daily_summary['Expense']
        daily_summary = daily_summary.rename(columns={'Date Only': 'Date'})
        
        st.dataframe(daily_summary, use_container_width=True, hide_index=True)
        st.divider()

        st.subheader("Detailed Logs")
        display_df = filtered_df.sort_values(by="Timestamp", ascending=False).drop(columns=['Date Only'])
        display_df["Timestamp"] = display_df["Timestamp"].dt.strftime("%Y-%m-%d %I:%M %p")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
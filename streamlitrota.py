import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import random
import csv
from io import StringIO
import calendar

class Doctor:
    def __init__(self, name, preference=None):
        self.name = name
        self.shifts = []
        self.last_shift = None
        self.weekend_shifts = 0
        self.vacation_days = set()
        self.preference = preference

    def reset(self):
        self.shifts = []
        self.last_shift = None
        self.weekend_shifts = 0
        self.first_on_call = 0
        self.second_on_call = 0

class Schedule:
    def __init__(self, doctors, start_date, end_date):
        self.doctors = doctors
        self.start_date = start_date
        self.end_date = end_date
        self.schedule = {}

    def generate_schedule(self):
        for doctor in self.doctors:
            doctor.reset()
            doctor.first_on_call = 0
            doctor.second_on_call = 0

        # Shuffle the doctors list to randomize the initial order
        random.shuffle(self.doctors)

        current_date = self.start_date
        while current_date <= self.end_date:
            available_doctors = [d for d in self.doctors if self.is_available(d, current_date)]
            if len(available_doctors) < 2:
                st.warning(f"Warning: Not enough available doctors on {current_date}")
                available_doctors = [d for d in self.doctors if current_date not in d.vacation_days]

            if len(available_doctors) < 2:
                return False

            is_weekend = current_date.weekday() in [4, 5]  # Friday or Saturday
            
            # Sort doctors considering preferences and balance between 1st and 2nd on-call
            available_doctors.sort(key=lambda d: (
                d.weekend_shifts if is_weekend else len(d.shifts),
                d.last_shift or date.min,
                d.first_on_call - d.second_on_call,  # Balance between 1st and 2nd on-call
                random.random()  # Add a random factor to break ties
            ))

            first_on_call = available_doctors[0]
            second_on_call = available_doctors[1]

            # Swap if second doctor has a strong preference for 1st on-call
            if second_on_call.preference == '1st' and first_on_call.preference != '1st':
                first_on_call, second_on_call = second_on_call, first_on_call

            self.schedule[current_date] = [first_on_call, second_on_call]
            first_on_call.shifts.append(current_date)
            second_on_call.shifts.append(current_date)

            first_on_call.last_shift = current_date
            second_on_call.last_shift = current_date

            first_on_call.first_on_call += 1
            second_on_call.second_on_call += 1

            if is_weekend:
                first_on_call.weekend_shifts += 1
                second_on_call.weekend_shifts += 1

            current_date += timedelta(days=1)
        return True

    def is_available(self, doctor, date):
        if date in doctor.vacation_days:
            return False
        if doctor.last_shift is None:
            return True
        days_since_last_shift = (date - doctor.last_shift).days
        return days_since_last_shift > 1

    def get_dataframe(self):
        data = [
            {'Date': date, '1st On-Call': doctors[0].name, '2nd On-Call': doctors[1].name}
            for date, doctors in sorted(self.schedule.items())
        ]
        return pd.DataFrame(data)

    def get_doctor_statistics(self):
        stats = {doctor.name: {'1st On-Call': 0, '2nd On-Call': 0, 'Weekend On-Call': 0} for doctor in self.doctors}
        for date, doctors in self.schedule.items():
            stats[doctors[0].name]['1st On-Call'] += 1
            stats[doctors[1].name]['2nd On-Call'] += 1
            if date.weekday() in [4, 5]:  # Friday or Saturday
                stats[doctors[0].name]['Weekend On-Call'] += 1
                stats[doctors[1].name]['Weekend On-Call'] += 1
        
        # Calculate total on-calls
        for doctor_stats in stats.values():
            doctor_stats['Total On-Call'] = doctor_stats['1st On-Call'] + doctor_stats['2nd On-Call']
        
        return stats

# Initialize session state
if 'doctors' not in st.session_state:
    st.session_state.doctors = [
        Doctor("Raed Alghamdi"), Doctor("Saeed Alshahrani"), Doctor("Saeed Abdulnoor"),
        Doctor("Ahmad Abkar"), Doctor("Hazim Jokhadar"), Doctor("Mariah Alamri"),
        Doctor("Khalid Alroqi"), Doctor("Ban Alzaid"), Doctor("Rayyan Alyahya"),
        Doctor("Abdullah Alahmari"), Doctor("Abdullah Alsadoun"), Doctor("Mohammad Kamal"),
        Doctor("Adel Asiri"), Doctor("Abdulkarim Alshadookhi")
    ]

if 'schedule' not in st.session_state:
    st.session_state.schedule = None

# Streamlit app
st.title("SCOT Rota Generator")

# Main content area with tabs
tab1, tab2, tab3, tab4 = st.tabs(["📅 Generate Schedule", "👨‍⚕️ Manage Doctors", "🗓️ Vacation Days", "🎯 Preferences"])

with tab1:
    st.header("Schedule Settings")
    
    # Get current date and calculate next month
    current_date = datetime.now()
    next_month = current_date.replace(day=1) + timedelta(days=32)
    default_month = next_month.month
    default_year = next_month.year

    # Create a list of month names
    month_names = list(calendar.month_name)[1:]

    # Month selection defaulting to next month
    month = st.selectbox("Select Month", range(1, 13), 
                         format_func=lambda x: month_names[x-1],
                         index=default_month-1)
    
    # Year selection defaulting to next month's year
    year = st.selectbox("Select Year", 
                        range(current_date.year, current_date.year + 5),
                        index=default_year - current_date.year)

    if st.button("🚀 Generate Schedule"):
        start_date = datetime(year, month, 1).date()
        end_date = (datetime(year, month + 1, 1) - timedelta(days=1)).date() if month < 12 else datetime(year, 12, 31).date()

        schedule = Schedule(st.session_state.doctors, start_date, end_date)
        
        progress_bar = st.progress(0)
        for i in range(100):
            # Simulate progress
            progress_bar.progress(i + 1)
        
        if schedule.generate_schedule():
            st.session_state.schedule = schedule
            st.success("✅ Schedule generated successfully!")
        else:
            st.error("❌ Failed to generate schedule. Please check vacation days.")

    if st.session_state.schedule:
        st.subheader("Generated Schedule")
        df = st.session_state.schedule.get_dataframe()
        st.table(df)

        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="clinical_rota_schedule.csv",
            mime="text/csv",
        )

        st.subheader("Doctor Statistics")
        stats = st.session_state.schedule.get_doctor_statistics()
        stats_df = pd.DataFrame.from_dict(stats, orient='index')
        stats_df = stats_df.reset_index().rename(columns={'index': 'Doctor'})
        stats_df = stats_df.sort_values('Total On-Call', ascending=False)
        st.table(stats_df)

with tab2:
    st.header("Manage Doctors")
    doctor_name = st.selectbox("Select Doctor", [doctor.name for doctor in st.session_state.doctors])
    doctor = next((d for d in st.session_state.doctors if d.name == doctor_name), None)

    if doctor:
        action = st.radio("Action", ["Set Preference", "Add Vacation", "Delete Vacation"])
        
        if action == "Set Preference":
            preference = st.radio("Select Preference", ["No Preference", "1st On-Call", "2nd On-Call"])
            if st.button("Set Preference"):
                doctor.preference = None if preference == "No Preference" else preference.split()[0].lower()
                st.success(f"✅ Preference set for {doctor_name}: {preference}")
        
        elif action == "Add Vacation":
            vacation_start = st.date_input("Vacation Start Date")
            vacation_end = st.date_input("Vacation End Date", min_value=vacation_start)
            if st.button("Add Vacation"):
                vacation_days = [vacation_start + timedelta(days=x) for x in range((vacation_end - vacation_start).days + 1)]
                doctor.vacation_days.update(vacation_days)
                st.success(f"✅ Vacation days from {vacation_start} to {vacation_end} added for {doctor_name}")
        
        elif action == "Delete Vacation":
            if doctor.vacation_days:
                vacation_to_delete = st.selectbox("Select Vacation to Delete", sorted(doctor.vacation_days))
                if st.button("Delete Vacation"):
                    doctor.vacation_days.remove(vacation_to_delete)
                    st.success(f"✅ Vacation day {vacation_to_delete} deleted for {doctor_name}")
            else:
                st.info("No vacation days to delete for this doctor.")

with tab3:
    st.header("Vacation Days")
    for doctor in st.session_state.doctors:
        if doctor.vacation_days:
            with st.expander(f"{doctor.name}'s Vacation Days"):
                vacation_days = sorted(doctor.vacation_days)
                for day in vacation_days:
                    col1, col2 = st.columns([3, 1])
                    col1.write(day.strftime("%Y-%m-%d"))
                    if col2.button("Delete", key=f"del_{doctor.name}_{day}"):
                        doctor.vacation_days.remove(day)
                        st.success(f"✅ Vacation day {day} deleted for {doctor.name}")
                        st.rerun()

with tab4:
    st.header("Doctor Preferences")
    preferences_data = [
        {'Doctor': doctor.name, 'Preference': doctor.preference if doctor.preference else 'No Preference'}
        for doctor in st.session_state.doctors
    ]
    st.table(pd.DataFrame(preferences_data))

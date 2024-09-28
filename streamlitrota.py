import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import random
import calendar
from typing import List, Dict, Set
from collections import defaultdict, deque

class Doctor:
    def __init__(self, name: str, team: str):
        self.name = name
        self.team = team
        self.shifts: List[date] = []
        self.last_shift: date = None
        self.vacation_days: Set[date] = set()
        self.mobile_team_days: Set[date] = set()

    def reset(self):
        self.shifts = []
        self.last_shift = None

    def to_dict(self):
        return {
            'name': self.name,
            'team': self.team,
            'shifts': [d.isoformat() if d else None for d in self.shifts],
            'last_shift': self.last_shift.isoformat() if self.last_shift else None,
            'vacation_days': [d.isoformat() for d in self.vacation_days],
            'mobile_team_days': [d.isoformat() for d in self.mobile_team_days]
        }

    @classmethod
    def from_dict(cls, data):
        doctor = cls(data['name'], data['team'])
        doctor.shifts = [date.fromisoformat(d) if d else None for d in data['shifts']]
        doctor.last_shift = date.fromisoformat(data['last_shift']) if data['last_shift'] else None
        doctor.vacation_days = set(date.fromisoformat(d) for d in data['vacation_days'])
        doctor.mobile_team_days = set(date.fromisoformat(d) for d in data['mobile_team_days'])
        return doctor

    @classmethod
    def from_object(cls, obj):
        if isinstance(obj, Doctor):
            return obj
        elif isinstance(obj, dict):
            return cls.from_dict(obj)
        else:
            doctor = cls(obj.name, obj.team)
            doctor.shifts = obj.shifts
            doctor.last_shift = obj.last_shift
            doctor.vacation_days = set(obj.vacation_days)
            doctor.mobile_team_days = set(obj.mobile_team_days)
            return doctor

class Schedule:
    def __init__(self, doctors: List[Doctor], start_date: date, end_date: date, max_oncalls_per_week: int, min_days_between_oncalls: int):
        self.doctors = doctors
        self.start_date = start_date
        self.end_date = end_date
        self.schedule: Dict[date, List[Doctor]] = {}
        self.max_oncalls_per_week = max_oncalls_per_week
        self.min_days_between_oncalls = min_days_between_oncalls
        self.weekend_cooldown = 14  # Minimum days between weekend on-calls for a doctor

    def generate_schedule(self) -> bool:
        for doctor in self.doctors:
            doctor.reset()

        current_date = self.start_date
        while current_date <= self.end_date:
            if current_date.weekday() in [4, 5]:  # Friday or Saturday
                self._assign_weekend_oncall(current_date)
            else:
                self._assign_weekday_oncall(current_date)
            current_date += timedelta(days=1)

        self._balance_schedule()
        return True

    def _assign_weekend_oncall(self, date: date):
        available_doctors = self._get_available_doctors(date)
        available_doctors = [d for d in available_doctors if self._is_weekend_eligible(d, date)]
        if len(available_doctors) < 2:
            raise ValueError(f"Not enough available doctors for weekend on-call on {date}")
        
        selected_doctors = self._select_doctors(available_doctors, 2, date)
        self.schedule[date] = selected_doctors
        for doctor in selected_doctors:
            doctor.shifts.append(date)
            doctor.last_shift = date

    def _assign_weekday_oncall(self, date: date):
        available_doctors = self._get_available_doctors(date)
        if not available_doctors:
            raise ValueError(f"No available doctors for weekday on-call on {date}")
        
        selected_doctor = self._select_doctors(available_doctors, 1, date)[0]
        self.schedule[date] = [selected_doctor]
        selected_doctor.shifts.append(date)
        selected_doctor.last_shift = date

    def _get_available_doctors(self, date: date) -> List[Doctor]:
        return [d for d in self.doctors if self._is_available(d, date)]

    def _is_available(self, doctor: Doctor, date: date) -> bool:
        if date in doctor.vacation_days or date in doctor.mobile_team_days:
            return False
        if doctor.last_shift is None:
            return True
        days_since_last_shift = (date - doctor.last_shift).days
        shifts_this_week = sum(1 for shift in doctor.shifts if 0 <= (date - shift).days < 7)
        return days_since_last_shift > self.min_days_between_oncalls and shifts_this_week < self.max_oncalls_per_week

    def _is_weekend_eligible(self, doctor: Doctor, date: date) -> bool:
        last_weekend_oncall = max((d for d in doctor.shifts if d.weekday() in [4, 5]), default=None)
        if last_weekend_oncall is None:
            return True
        return (date - last_weekend_oncall).days >= self.weekend_cooldown

    def _select_doctors(self, available_doctors: List[Doctor], count: int, date: date) -> List[Doctor]:
        def fairness_score(doctor: Doctor) -> float:
            total_oncalls = len(doctor.shifts)
            weekend_oncalls = sum(1 for d in doctor.shifts if d.weekday() in [4, 5])
            weekday_oncalls = total_oncalls - weekend_oncalls
            days_since_last_shift = (date - doctor.last_shift).days if doctor.last_shift else float('inf')
            
            score = -total_oncalls * 10  # Prioritize doctors with fewer total on-calls
            if date.weekday() in [4, 5]:  # Weekend
                score -= weekend_oncalls * 5  # Prioritize doctors with fewer weekend on-calls
            else:  # Weekday
                score -= weekday_oncalls * 5  # Prioritize doctors with fewer weekday on-calls
            
            score += days_since_last_shift * 0.5  # Slightly prioritize doctors who haven't had an on-call recently
            return score

        sorted_doctors = sorted(available_doctors, key=lambda d: (fairness_score(d) + random.random() * 0.1), reverse=True)
        
        if count > 1:
            first_doctor = sorted_doctors[0]
            other_team_doctors = [d for d in sorted_doctors[1:] if d.team != first_doctor.team]
            if other_team_doctors:
                return [first_doctor] + [other_team_doctors[0]]
            else:
                return sorted_doctors[:count]
        else:
            return sorted_doctors[:count]

    def _balance_schedule(self):
        for _ in range(3):  # Perform multiple passes to improve balance
            oncall_counts = {doctor: len(doctor.shifts) for doctor in self.doctors}
            avg_oncalls = sum(oncall_counts.values()) / len(self.doctors)
            
            for date, doctors in self.schedule.items():
                for i, doctor in enumerate(doctors):
                    if oncall_counts[doctor] > avg_oncalls + 1:
                        available_doctors = self._get_available_doctors(date)
                        underworked_doctors = [d for d in available_doctors if oncall_counts[d] < avg_oncalls - 1]
                        if underworked_doctors:
                            new_doctor = min(underworked_doctors, key=lambda d: oncall_counts[d])
                            self.schedule[date][i] = new_doctor
                            doctor.shifts.remove(date)
                            new_doctor.shifts.append(date)
                            new_doctor.last_shift = date
                            oncall_counts[doctor] -= 1
                            oncall_counts[new_doctor] += 1
                            
    def get_dataframe(self) -> pd.DataFrame:
        data = []
        for date, doctors in sorted(self.schedule.items()):
            row = {
                'Date': date,
                'Day': date.strftime('%A'),
                'On-Call 1': doctors[0].name if doctors else '',
                'On-Call 2': doctors[1].name if len(doctors) > 1 else ''
            }
            
            # Add mobile rota doctors
            mobile_doctors = [d.name for d in self.doctors if date in d.mobile_team_days]
            row['Mobile Rota'] = ', '.join(mobile_doctors) if mobile_doctors else ''
            
            data.append(row)
        
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        return df

    def get_doctor_statistics(self) -> Dict[str, Dict[str, int]]:
        stats = {}
        for doctor in self.doctors:
            weekend_oncalls = sum(1 for date in doctor.shifts if date.weekday() in [4, 5])  # Friday or Saturday
            weekday_oncalls = len(doctor.shifts) - weekend_oncalls
            stats[doctor.name] = {
                'Total On-Calls': len(doctor.shifts),
                'Weekend On-Calls': weekend_oncalls,
                'Weekday On-Calls': weekday_oncalls,
                'Team': doctor.team,
                'Vacation Days': len(doctor.vacation_days),
                'Mobile Team Days': len(doctor.mobile_team_days)
            }
        return stats

def init_session_state():
    if 'doctors' not in st.session_state:
        st.session_state.doctors = [
            Doctor("Rayyan Alyahya", "Team A"), Doctor("Abdullah Alahmari", "Team A"),
            Doctor("Abdulkarim Alshadookhi", "Team A"), Doctor("Ahmad Abkar", "Team A"),
            Doctor("Ban Alzaid", "Team A"), Doctor("Mohammad Kamal", "Team A"),
            Doctor("Hazim Jokhadar", "Team B"), Doctor("Saeed Alshahrani", "Team B"),
            Doctor("Abdullah Alsadoun", "Team B"), Doctor("Saeed Abdulnoor", "Team B"),
            Doctor("Raed Alghamdi", "Team B"), Doctor("Adel Asiri", "Team B"),
            Doctor("Khalid Alroqi", "Allocation Team"), Doctor("Mariah Alamri", "Allocation Team")
        ]
    else:
        st.session_state.doctors = [Doctor.from_object(d) for d in st.session_state.doctors]
    
    if 'schedule' not in st.session_state:
        st.session_state.schedule = None
    if 'vacation_data' not in st.session_state:
        st.session_state.vacation_data = {doctor.name: list(doctor.vacation_days) for doctor in st.session_state.doctors}
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "Generate Schedule"

def main():
    st.set_page_config(page_title="SCOT Rota Generator", page_icon="🏥", layout="wide")
    
    init_session_state()  # Call the initialization function
    
    # Custom CSS for improved styling
    st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .stButton>button {
        width: 100%;
        height: 50px;
        margin: 5px 0;
        border-radius: 5px;
        border: 1px solid #ccc;
        background-color: #f0f0f0;
        transition: background-color 0.3s;
    }
    .stButton>button:hover {
        background-color: #e0e0e0;
    }
    .stDataFrame {
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("SCOT Rota Generator")

    tabs = ["Generate Schedule", "Manage Doctors", "Mobile Team", "Statistics"]
    
    selected_tab = st.tabs(tabs)

    for i, tab in enumerate(tabs):
        with selected_tab[i]:
            if tab == "Generate Schedule":
                generate_schedule_tab()
            elif tab == "Manage Doctors":
                manage_doctors_tab()
            elif tab == "Mobile Team":
                mobile_team_tab()
            elif tab == "Statistics":
                statistics_tab()

def generate_schedule_tab():
    st.header("Generate Schedule")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Schedule Start Date", min_value=date.today())
    with col2:
        end_date = st.date_input("Schedule End Date", min_value=start_date)
    
    max_oncalls = st.number_input("Maximum On-Calls per Week", min_value=1, max_value=7, value=2)
    min_days_between = st.number_input("Minimum Days Between On-Calls", min_value=1, max_value=14, value=3)
    
    if st.button("Generate Schedule"):
        schedule = Schedule(st.session_state.doctors, start_date, end_date, max_oncalls, min_days_between)
        
        if schedule.generate_schedule():
            st.session_state.schedule = schedule  # Store the generated schedule in session state
            st.success("Schedule generated successfully!")
            df = schedule.get_dataframe()
            
            # Display the dataframe with custom column widths
            st.dataframe(
                df,
                column_config={
                    "Date": st.column_config.DateColumn(width="medium"),
                    "Day": st.column_config.TextColumn(width="small"),
                    "On-Call 1": st.column_config.TextColumn(width="medium"),
                    "On-Call 2": st.column_config.TextColumn(width="medium"),
                    "Mobile Rota": st.column_config.TextColumn(width="large"),
                },
                hide_index=True,
            )
        else:
            st.error("Failed to generate a valid schedule. Please try adjusting the parameters.")

def manage_doctors_tab():
    st.header("Manage Doctor Vacations")

    # Initialize vacation data in session state if it doesn't exist
    if 'vacation_data' not in st.session_state:
        st.session_state.vacation_data = {doctor.name: list(doctor.vacation_days) for doctor in st.session_state.doctors}

    # Group doctors by team
    teams = {"Team A": [], "Team B": [], "Allocation Team": []}
    for doctor in st.session_state.doctors:
        teams[doctor.team].append(doctor)

    # Display doctors by team with their vacations
    for team, doctors in teams.items():
        st.subheader(f"{team} Doctors")
        for doctor in doctors:
            with st.expander(f"{doctor.name}'s Vacations"):
                # Display current vacations
                if st.session_state.vacation_data[doctor.name]:
                    for vacation in sorted(st.session_state.vacation_data[doctor.name]):
                        col1, col2 = st.columns([3, 1])
                        col1.write(vacation.strftime('%Y-%m-%d'))
                        if col2.button("Delete", key=f"delete_{doctor.name}_{vacation}"):
                            st.session_state.vacation_data[doctor.name].remove(vacation)
                            st.success(f"Deleted vacation for {doctor.name} on {vacation}")
                else:
                    st.write("No vacations scheduled.")

                # Add new vacation
                st.write("Add new vacation:")
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("Start date", key=f"start_{doctor.name}")
                with col2:
                    end_date = st.date_input("End date", key=f"end_{doctor.name}")
                
                if st.button("Add Vacation", key=f"add_button_{doctor.name}"):
                    if start_date <= end_date:
                        new_vacation_days = set(start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1))
                        existing_vacations = set(st.session_state.vacation_data[doctor.name])
                        overlapping_days = existing_vacations.intersection(new_vacation_days)
                        if overlapping_days:
                            st.warning(f"The following dates overlap with existing vacations: {', '.join(d.strftime('%Y-%m-%d') for d in sorted(overlapping_days))}")
                        else:
                            st.session_state.vacation_data[doctor.name].extend(new_vacation_days)
                            st.success(f"Added vacation for {doctor.name} from {start_date} to {end_date}")
                    else:
                        st.warning("End date must be after or equal to start date.")

    # Add a section to view all vacations in a single table
    st.subheader("All Vacations")
    all_vacations = []
    for doctor_name, vacations in st.session_state.vacation_data.items():
        doctor = next(d for d in st.session_state.doctors if d.name == doctor_name)
        for vacation in vacations:
            all_vacations.append({"Doctor": doctor_name, "Team": doctor.team, "Vacation Date": vacation})
    
    if all_vacations:
        df = pd.DataFrame(all_vacations)
        df = df.sort_values(by=["Vacation Date", "Team", "Doctor"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No vacations scheduled for any doctor.")

    # Update the actual Doctor objects with the vacation data
    for doctor in st.session_state.doctors:
        doctor.vacation_days = set(st.session_state.vacation_data[doctor.name])

def mobile_team_tab():
    st.header("Mobile Team Management")

    # Initialize mobile_team_rotations in session state if it doesn't exist
    if 'mobile_team_rotations' not in st.session_state:
        st.session_state.mobile_team_rotations = {}

    # Doctor selection
    all_doctors = [doctor.name for doctor in st.session_state.doctors]
    selected_doctors = st.multiselect("Select Doctors for Mobile Team Rotation", options=all_doctors)

    # Date selection
    today = date.today()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=today, min_value=today, key="mobile_team_start_date")
    with col2:
        # Ensure the end_date default is not before start_date
        end_date = st.date_input("End Date", value=max(today, start_date), min_value=start_date, key="mobile_team_end_date")

    # Add rotation button
    if st.button("Add Mobile Team Rotation"):
        if selected_doctors and start_date <= end_date:
            current_date = start_date
            while current_date <= end_date:
                if current_date not in st.session_state.mobile_team_rotations:
                    st.session_state.mobile_team_rotations[current_date] = []
                st.session_state.mobile_team_rotations[current_date].extend(selected_doctors)
                
                # Update mobile_team_days for each selected doctor
                for doctor_name in selected_doctors:
                    doctor = next(d for d in st.session_state.doctors if d.name == doctor_name)
                    doctor.mobile_team_days.add(current_date)
                
                current_date += timedelta(days=1)
            st.success(f"Added rotation for selected doctors from {start_date} to {end_date}")
        else:
            st.warning("Please select at least one doctor and ensure the end date is not before the start date.")

    # Display current rotations
    st.subheader("Current Mobile Team Rotations")
    if st.session_state.mobile_team_rotations:
        rotation_data = []
        for rotation_date, doctors in sorted(st.session_state.mobile_team_rotations.items()):
            rotation_data.append({
                "Date": rotation_date,
                "Doctors": ", ".join(doctors)
            })
        
        df = pd.DataFrame(rotation_data)
        st.dataframe(df, use_container_width=True)

        # Delete rotations
        if st.button("Delete All Rotations"):
            st.session_state.mobile_team_rotations = {}
            # Clear mobile_team_days for all doctors
            for doctor in st.session_state.doctors:
                doctor.mobile_team_days.clear()
            st.success("All rotations deleted")
            st.rerun()
    else:
        st.info("No mobile team rotations scheduled")

def statistics_tab():
    st.header("Statistics")

    if 'schedule' in st.session_state and st.session_state.schedule:
        stats = st.session_state.schedule.get_doctor_statistics()
        stats_df = pd.DataFrame.from_dict(stats, orient='index')
        
        # Reorder columns
        column_order = ['Team', 'Total On-Calls', 'Weekend On-Calls', 'Weekday On-Calls', 'Vacation Days', 'Mobile Team Days']
        stats_df = stats_df[column_order]
        
        st.subheader("Doctor Statistics")
        st.dataframe(stats_df)

        # Calculate and display overall statistics
        total_oncalls = stats_df['Total On-Calls'].sum()
        total_weekend_oncalls = stats_df['Weekend On-Calls'].sum()
        total_weekday_oncalls = stats_df['Weekday On-Calls'].sum()

        st.subheader("Overall Statistics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total On-Calls", total_oncalls)
        col2.metric("Total Weekend On-Calls", total_weekend_oncalls)
        col3.metric("Total Weekday On-Calls", total_weekday_oncalls)

        # Display chart
        st.subheader("On-Call Distribution")
        chart_data = stats_df[['Weekday On-Calls', 'Weekend On-Calls']]
        st.bar_chart(chart_data)

    else:
        st.info("Please generate a schedule first to view statistics.")

if __name__ == "__main__":
    main()

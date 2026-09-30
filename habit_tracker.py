import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

st.set_page_config(page_title="October Habit Tracker", page_icon="✅", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
DAYS = list(range(1, 32))  # October has 31 days
DEFAULT_HABITS = ["wake up at 6", "meditation", "Drink water", "Sleep by 11pm", "Exercise","No sugar","Journaling","Read 10 pages", "Gym"]

@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open("October Habit Tracker").sheet1

def save_data(df):
    sheet = get_sheet()
    rows = [["Habit"] + DAYS]
    for habit, row in df.iterrows():
        rows.append([habit] + [bool(v) for v in row])
    sheet.clear()
    sheet.update(range_name="A1", values=rows)

def load_data():
    sheet = get_sheet()
    values = sheet.get_all_values()
    if len(values) < 2:  # sheet is empty, create the first table
        df = pd.DataFrame(False, index=DEFAULT_HABITS, columns=DAYS)
        save_data(df)
        return df
    habits = [r[0] for r in values[1:]]
    data = [[cell == "TRUE" for cell in r[1:32]] for r in values[1:]]
    return pd.DataFrame(data, index=habits, columns=DAYS)

df = load_data()
st.sidebar.header("⚙️ Manage habits")

new_habit = st.sidebar.text_input("New habit")
if st.sidebar.button("➕ Add habit"):
    name = new_habit.strip()
    if not name:
        st.sidebar.warning("Type a habit name first.")
    elif name in df.index:
        st.sidebar.warning("That habit already exists.")
    else:
        df.loc[name] = False
        save_data(df)
        st.session_state.pop("grid", None)
        st.rerun()

to_remove = st.sidebar.selectbox("Remove a habit", ["-"] + list(df.index))
if st.sidebar.button("🗑️ Remove habit") and to_remove != "-":
    df = df.drop(index=to_remove)
    save_data(df)
    st.session_state.pop("grid", None)
    st.rerun()

st.title("✅ October Habit Tracker")
st.header("For Sunny Chadha")
st.caption("Tick your habits, then press Save.")

edited = st.data_editor(
    df.rename(columns=str),
    column_config={
        str(d): st.column_config.CheckboxColumn(str(d), default=False) for d in DAYS
    },
    key="grid",
)

if st.button("💾 Save progress", type="primary"):
    save_data(edited)
    st.success("Saved to Google Sheets!")


st.divider()
st.subheader("📊 Progress")

# Chart 1: daily completion %
daily_pct = (edited.sum(axis=0) / len(edited) * 100).round(0)
daily_df = pd.DataFrame({"Day": daily_pct.index.astype(int), "Completion %": daily_pct.values})
fig1 = px.bar(daily_df, x="Day", y="Completion %", title="Daily completion %", range_y=[0, 100])
st.plotly_chart(fig1, use_container_width=True)

# Chart 2: days completed per habit
habit_totals = edited.sum(axis=1).sort_values()
habit_df = pd.DataFrame({"Habit": habit_totals.index, "Days done": habit_totals.values})
fig2 = px.bar(habit_df, x="Days done", y="Habit", orientation="h",
              title="Days completed per habit", range_x=[0, 31])
st.plotly_chart(fig2, use_container_width=True)

from datetime import date

# Which day of October counts as "today"
_t = date.today()
if _t.year == 2026 and _t.month == 10:
    today_day = _t.day
elif _t > date(2026, 10, 31):
    today_day = 31
else:
    today_day = 1  # before October, use day 1 for testing

def get_streaks(row, upto):
    vals = [bool(row[str(d)]) for d in range(1, upto + 1)]
    best = run = 0
    for v in vals:
        run = run + 1 if v else 0
        best = max(best, run)
    i = upto - 1
    if not vals[i] and upto > 1:  # today not ticked yet, don't break the streak
        i -= 1
    current = 0
    while i >= 0 and vals[i]:
        current += 1
        i -= 1
    return current, best

st.divider()
st.subheader("🔥 Today & Streaks")

done_today = int(edited[str(today_day)].sum())
total = len(edited)
st.progress(done_today / total, text=f"Day {today_day}: {done_today}/{total} habits done")

cols = st.columns(3)
for i, (habit, row) in enumerate(edited.iterrows()):
    current, best = get_streaks(row, today_day)
    with cols[i % 3]:
        st.metric(habit, f"{current} day streak", f"Best: {best}", delta_color="off")

import calendar
import plotly.graph_objects as go

st.divider()
st.subheader("🗓️ Calendar heatmap")

pct = (edited.sum(axis=0) / len(edited) * 100).round(0)  # keys are "1".."31"
weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(2026, 10)  # Monday first

z, labels = [], []
for w in weeks:
    z.append([pct[str(d)] if d != 0 else None for d in w])
    labels.append([str(d) if d != 0 else "" for d in w])

fig3 = go.Figure(go.Heatmap(
    z=z,
    text=labels,
    texttemplate="%{text}",
    x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    y=[f"Week {i + 1}" for i in range(len(weeks))],
    colorscale=[[0, "#1f2937"], [1, "#22c55e"]],
    zmin=0, zmax=100,
    xgap=4, ygap=4,
    hovertemplate="Day %{text}: %{z}% done<extra></extra>",
    colorbar=dict(title="%"),
))
fig3.update_yaxes(autorange="reversed")
fig3.update_layout(title="Daily completion (darker = more habits done)", height=400)
st.plotly_chart(fig3, use_container_width=True)

st.divider()
st.subheader("💡 Insights")

cols_so_far = [str(d) for d in range(1, today_day + 1)]
sub = edited[cols_so_far]

if sub.values.sum() == 0:
    st.info("Tick some habits to see your insights!")
else:
    overall = round(sub.values.mean() * 100)
    totals = sub.sum(axis=1)

    # Average completion for each weekday
    day_pct = sub.mean(axis=0)
    by_weekday = {}
    for d in range(1, today_day + 1):
        wd = date(2026, 10, d).weekday()
        by_weekday.setdefault(wd, []).append(day_pct[str(d)])
    best_wd = max(by_weekday, key=lambda k: sum(by_weekday[k]) / len(by_weekday[k]))
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall completion", f"{overall}%")
    c2.metric("Most consistent habit", totals.idxmax())
    c3.metric("Needs attention", totals.idxmin())
    c4.metric("Best day of week", weekday_names[best_wd])

# Motivational message based on today's progress
ratio = done_today / total
if ratio == 1:
    st.success("🏆 Perfect day! All habits done. Keep it up!")
elif ratio >= 0.5:
    st.info("💪 Over halfway there today. Finish strong!")
elif ratio > 0:
    st.warning("🌱 Good start. A few more ticks and you're on track.")
else:
    st.warning("⏰ Nothing ticked yet today. Start with the easiest habit!")
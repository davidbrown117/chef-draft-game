import streamlit as st
import sqlite3
import json
import os

# --- 0. APP CONFIGURATION & CONSTANTS ---
os.makedirs("images", exist_ok=True)

TEAM_1 = "Team Alpha"
TEAM_2 = "Team Bravo"
TEAM_3 = "Team Charlie"
ALL_TEAMS = [TEAM_1, TEAM_2, TEAM_3]

MEALS = [
    "Saturday Breakfast", "Saturday Lunch", "Saturday Dinner",
    "Sunday Breakfast", "Sunday Lunch", "Sunday Dinner"
]

# --- 1. DATABASE SETUP ---
conn = sqlite3.connect("draft.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS players (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, attributes TEXT, image_path TEXT, team TEXT DEFAULT 'None')")
cursor.execute("CREATE TABLE IF NOT EXISTS teams (name TEXT PRIMARY KEY, steal_used INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS meals (id INTEGER PRIMARY KEY AUTOINCREMENT, meal_name TEXT UNIQUE, team TEXT DEFAULT 'None')")
cursor.execute("CREATE TABLE IF NOT EXISTS action_log (id INTEGER PRIMARY KEY AUTOINCREMENT, log_text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")

for team in ALL_TEAMS:
    cursor.execute("INSERT OR IGNORE INTO teams (name, steal_used) VALUES (?, 0)", (team,))
for meal in MEALS:
    cursor.execute("INSERT OR IGNORE INTO meals (meal_name, team) VALUES (?, 'None')", (meal,))
conn.commit()

def log_action(action_text):
    cursor.execute("INSERT INTO action_log (log_text) VALUES (?)", (action_text,))
    conn.commit()

# --- APP UI START ---
st.set_page_config(page_title="Chef Draft", layout="wide")
st.title("🍳 Chef Draft: Captain's Pick")

# --- SIDEBAR ROLE UNLOCKER ---
st.sidebar.header("🔑 Access Control")
access_key = st.sidebar.text_input("Enter Passcode for Captain/Admin Access:", type="password")

# Determine role based on passcode
is_captain = (access_key == "chef2026" or access_key == "admin2026")
is_admin = (access_key == "admin2026")

if is_admin:
    st.sidebar.success("Logged in as Admin")
elif is_captain:
    st.sidebar.success("Logged in as Captain")
else:
    st.sidebar.info("Viewing as Participant")

# --- 2. PLAYER REGISTRATION (VISIBLE TO ALL) ---
with st.expander("📝 Player Registration (Click to Open)"):
    with st.form("registration_form", clear_on_submit=True):
        new_name = st.text_input("Chef Name:")
        uploaded_file = st.file_uploader("Upload a Headshot (Optional)", type=["jpg", "jpeg", "png"])
        st.write("Enter up to 5 stats:")
        
        attributes_data = []
        for i in range(5):
            col1, col2 = st.columns(2)
            with col1:
                key_input = st.text_input(f"Attribute {i+1}", key=f"attr_key_{i}")
            with col2:
                val_input = st.text_input(f"Value {i+1}", key=f"attr_val_{i}")
            attributes_data.append((key_input, val_input))
        
        if st.form_submit_button("Register for Draft"):
            if new_name.strip() == "":
                st.error("Please provide at least a Chef Name!")
            else:
                attribute_dict = {k.strip(): v.strip() for k, v in attributes_data if k.strip() != "" and v.strip() != ""}
                json_attributes = json.dumps(attribute_dict)
                
                image_path = None
                if uploaded_file is not None:
                    file_ext = uploaded_file.name.split('.')[-1]
                    image_path = f"images/{new_name.strip().replace(' ', '_')}.{file_ext}"
                    with open(image_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                try:
                    cursor.execute("INSERT INTO players (name, attributes, image_path) VALUES (?, ?, ?)", (new_name.strip(), json_attributes, image_path))
                    conn.commit()
                    log_action(f"Player Registered: {new_name.strip()}")
                    st.success(f"Chef {new_name} successfully registered!")
                except sqlite3.IntegrityError:
                    st.error("That chef name is already registered!")

st.divider()

# --- 3. THE DRAFT BOARD (CAPTAINS & ADMINS ONLY) ---
if is_captain:
    st.header("📋 Captain's Draft Console")
    draft_tab, steal_tab, meal_tab = st.tabs(["✅ Draft a Chef", "🥷 Execute a Steal", "🍽️ Draft Meals"])

    # (Draft, Steal, and Meal tab internal logic remains exactly as written previously...)
    with draft_tab:
        cursor.execute("SELECT name, attributes, image_path FROM players WHERE team = 'None'")
        available_players = cursor.fetchall()
        if len(available_players) > 0:
            player_names = [p[0] for p in available_players]
            selected_name = st.selectbox("Select a chef to view and draft:", player_names)
            selected_player_data = next(p for p in available_players if p[0] == selected_name)
            with st.container(border=True): 
                prof_col1, prof_col2 = st.columns([1, 2])
                with prof_col1:
                    if selected_player_data[2] and os.path.exists(selected_player_data[2]): st.image(selected_player_data[2], width=120)
                    else: st.write("*(No photo)*")
                with prof_col2:
                    display_dict = json.loads(selected_player_data[1])
                    for key, value in display_dict.items(): st.write(f"- **{key}:** {value}")
            team_choice = st.radio("Draft chef to which team?", ALL_TEAMS, horizontal=True)
            if st.button("Draft Chef!", type="primary"): 
                cursor.execute("UPDATE players SET team = ? WHERE name = ?", (team_choice, selected_name))
                log_action(f"DRAFT: {team_choice} drafted Chef {selected_name}")
                st.rerun()
        else:
            st.info("No available chefs in the pool.")

    with steal_tab:
        cursor.execute("SELECT name FROM teams WHERE steal_used = 0")
        eligible_stealers = [row[0] for row in cursor.fetchall()]
        if eligible_stealers:
            stealing_team = st.selectbox("Which team is using their Steal?", eligible_stealers)
            cursor.execute("SELECT name, team FROM players WHERE team != 'None' AND team != ?", (stealing_team,))
            stealable_players = cursor.fetchall()
            if stealable_players:
                target_options = [f"{p[0]} (from {p[1]})" for p in stealable_players]
                target_selection = st.selectbox("Who are they stealing?", target_options)
                if st.button("Execute Steal!", type="primary"):
                    target_name = target_selection.split(" (from ")[0]
                    old_team = target_selection.split(" (from ")[1].replace(")", "")
                    cursor.execute("UPDATE players SET team = ? WHERE name = ?", (stealing_team, target_name))
                    cursor.execute("UPDATE teams SET steal_used = 1 WHERE name = ?", (stealing_team,))
                    log_action(f"STEAL: {stealing_team} stole Chef {target_name} from {old_team}!")
                    st.rerun()
            else: st.info("No one has been drafted yet to steal!")
        else: st.warning("All teams have used their one steal!")

    with meal_tab:
        cursor.execute("SELECT meal_name FROM meals WHERE team = 'None'")
        available_meals = [row[0] for row in cursor.fetchall()]
        if len(available_meals) > 0:
            selected_meal = st.selectbox("Select a meal to draft:", available_meals)
            meal_team_choice = st.radio("Draft meal to which team?", ALL_TEAMS, horizontal=True)
            if st.button("Draft Meal!", type="primary"):
                cursor.execute("UPDATE meals SET team = ? WHERE meal_name = ?", (meal_team_choice, selected_meal))
                log_action(f"MEAL DRAFT: {meal_team_choice} took responsibility for {selected_meal}")
                st.rerun()
        else: st.success("All meals have been assigned for the weekend!")

    st.divider()

# --- 4. SHOW THE TEAMS (VISIBLE TO ALL) ---
st.header("🔪 Current Kitchen Brigades")
col1, col2, col3 = st.columns(3)

def display_team(team_name):
    st.markdown("##### 👨‍🍳 Chefs")
    cursor.execute("SELECT name, attributes, image_path FROM players WHERE team = ?", (team_name,))
    team_players = cursor.fetchall()
    if not team_players: st.write("*No chefs drafted yet.*")
    for p in team_players:
        with st.container(border=True): 
            st.markdown(f"**{p[0]}**")
            roster_col1, roster_col2 = st.columns([1, 2])
            with roster_col1:
                if p[2] and os.path.exists(p[2]): st.image(p[2], width=60)
            with roster_col2:
                attr_dict = json.loads(p[1])
                for k, v in attr_dict.items(): st.write(f"- {k}: {v}")
    st.markdown("##### 🍽️ Assigned Meals")
    cursor.execute("SELECT meal_name FROM meals WHERE team = ?", (team_name,))
    team_meals = cursor.fetchall()
    if not team_meals: st.write("*No meals assigned yet.*")
    else:
        for m in team_meals: st.write(f"- {m[0]}")

with col1:
    st.subheader(f"🔴 {TEAM_1}")
    display_team(TEAM_1)
with col2:
    st.subheader(f"🔵 {TEAM_2}")
    display_team(TEAM_2)
with col3:
    st.subheader(f"🟢 {TEAM_3}")
    display_team(TEAM_3)

# --- 5. EMERGENCY UNDO (ADMINS ONLY) ---
if is_admin:
    st.divider()
    with st.expander("🚨 Admin Panel: Emergency Undo & Audit Log"):
        admin_col1, admin_col2 = st.columns(2)
        with admin_col1:
            st.subheader("Undo a Mistake")
            cursor.execute("SELECT name, team FROM players WHERE team != 'None'")
            drafted_players = cursor.fetchall()
            if len(drafted_players) > 0:
                undo_options = [f"{p[0]} (Current: {p[1]})" for p in drafted_players]
                selected_undo = st.selectbox("Return a CHEF to the pool:", undo_options)
                if st.button("Undo Chef Assignment"):
                    name_to_undo = selected_undo.split(" (Current:")[0]
                    cursor.execute("UPDATE players SET team = 'None' WHERE name = ?", (name_to_undo,))
                    log_action(f"UNDO: Chef {name_to_undo} was returned to the pool.")
                    st.rerun()
            st.write("---")
            cursor.execute("SELECT meal_name, team FROM meals WHERE team != 'None'")
            assigned_meals = cursor.fetchall()
            if len(assigned_meals) > 0:
                meal_undo_options = [f"{m[0]} (Current: {m[1]})" for m in assigned_meals]
                selected_meal_undo = st.selectbox("Return a MEAL to the pool:", meal_undo_options)
                if st.button("Undo Meal Assignment"):
                    meal_to_undo = selected_meal_undo.split(" (Current:")[0]
                    cursor.execute("UPDATE meals SET team = 'None' WHERE meal_name = ?", (meal_to_undo,))
                    log_action(f"UNDO: Meal '{meal_to_undo}' was returned to the pool.")
                    st.rerun()
        with admin_col2:
            st.subheader("Action Log")
            cursor.execute("SELECT timestamp, log_text FROM action_log ORDER BY id DESC LIMIT 20")
            logs = cursor.fetchall()
            if not logs: st.write("No actions taken yet.")
            else:
                log_display = "".join([f"[{log[0].split('.')[0]}] {log[1]}\n" for log in logs])
                st.code(log_display, language="text")
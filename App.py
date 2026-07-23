import streamlit as st
import json
import base64
from supabase import create_client, Client

# --- 0. APP CONFIGURATION & CONSTANTS ---
TEAM_1 = "Team Alpha"
TEAM_2 = "Team Bravo"
TEAM_3 = "Team Charlie"
ALL_TEAMS = [TEAM_1, TEAM_2, TEAM_3]

# --- 1. SUPABASE DATABASE SETUP ---
# Streamlit securely loads your API keys from the .streamlit/secrets.toml file
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

def log_action(action_text):
    supabase.table("action_log").insert({"log_text": action_text}).execute()

# --- APP UI START ---
st.set_page_config(page_title="Chef Draft", layout="wide")
st.title("🍳 Chef Draft: Captain's Pick")

# --- SIDEBAR ROLE UNLOCKER ---
st.sidebar.header("🔑 Access Control")
access_key = st.sidebar.text_input("Enter Passcode for Captain/Admin Access:", type="password")

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
                
                # MAGIC HAPPENS HERE: Convert image to a Base64 text string
                image_data_string = None
                if uploaded_file is not None:
                    bytes_data = uploaded_file.getvalue()
                    base64_encoded = base64.b64encode(bytes_data).decode('utf-8')
                    mime_type = uploaded_file.type
                    image_data_string = f"data:{mime_type};base64,{base64_encoded}"

                try:
                    supabase.table("players").insert({
                        "name": new_name.strip(),
                        "attributes": json_attributes,
                        "image_data": image_data_string
                    }).execute()
                    
                    log_action(f"Player Registered: {new_name.strip()}")
                    st.success(f"Chef {new_name} successfully registered!")
                except Exception as e:
                    st.error("That chef name is already registered or an error occurred!")

st.divider()

# --- 3. THE DRAFT BOARD (CAPTAINS & ADMINS ONLY) ---
if is_captain:
    st.header("📋 Captain's Draft Console")
    draft_tab, steal_tab, meal_tab = st.tabs(["✅ Draft a Chef", "🥷 Execute a Steal", "🍽️ Draft Meals"])

    with draft_tab:
        response = supabase.table("players").select("*").eq("team", "None").execute()
        available_players = response.data
        
        if len(available_players) > 0:
            player_names = [p["name"] for p in available_players]
            selected_name = st.selectbox("Select a chef to view and draft:", player_names)
            selected_player_data = next(p for p in available_players if p["name"] == selected_name)
            
            with st.container(border=True): 
                prof_col1, prof_col2 = st.columns([1, 2])
                with prof_col1:
                    if selected_player_data["image_data"]: 
                        st.image(selected_player_data["image_data"], width=120)
                    else: 
                        st.write("*(No photo)*")
                with prof_col2:
                    display_dict = json.loads(selected_player_data["attributes"])
                    for key, value in display_dict.items(): 
                        st.write(f"- **{key}:** {value}")
                        
            team_choice = st.radio("Draft chef to which team?", ALL_TEAMS, horizontal=True)
            if st.button("Draft Chef!", type="primary"): 
                supabase.table("players").update({"team": team_choice}).eq("name", selected_name).execute()
                log_action(f"DRAFT: {team_choice} drafted Chef {selected_name}")
                st.rerun()
        else:
            st.info("No available chefs in the pool.")

    with steal_tab:
        response = supabase.table("teams").select("name").eq("steal_used", 0).execute()
        eligible_stealers = [row["name"] for row in response.data]
        
        if eligible_stealers:
            stealing_team = st.selectbox("Which team is using their Steal?", eligible_stealers)
            response = supabase.table("players").select("name, team").neq("team", "None").neq("team", stealing_team).execute()
            stealable_players = response.data
            
            if stealable_players:
                target_options = [f"{p['name']} (from {p['team']})" for p in stealable_players]
                target_selection = st.selectbox("Who are they stealing?", target_options)
                
                if st.button("Execute Steal!", type="primary"):
                    target_name = target_selection.split(" (from ")[0]
                    old_team = target_selection.split(" (from ")[1].replace(")", "")
                    
                    supabase.table("players").update({"team": stealing_team}).eq("name", target_name).execute()
                    supabase.table("teams").update({"steal_used": 1}).eq("name", stealing_team).execute()
                    log_action(f"STEAL: {stealing_team} stole Chef {target_name} from {old_team}!")
                    st.rerun()
            else: 
                st.info("No one has been drafted yet to steal!")
        else: 
            st.warning("All teams have used their one steal!")

    with meal_tab:
        response = supabase.table("meals").select("meal_name").eq("team", "None").execute()
        available_meals = [row["meal_name"] for row in response.data]
        
        if len(available_meals) > 0:
            selected_meal = st.selectbox("Select a meal to draft:", available_meals)
            meal_team_choice = st.radio("Draft meal to which team?", ALL_TEAMS, horizontal=True)
            if st.button("Draft Meal!", type="primary"):
                supabase.table("meals").update({"team": meal_team_choice}).eq("meal_name", selected_meal).execute()
                log_action(f"MEAL DRAFT: {meal_team_choice} took responsibility for {selected_meal}")
                st.rerun()
        else: 
            st.success("All meals have been assigned for the weekend!")

    st.divider()

# --- 4. SHOW THE TEAMS (VISIBLE TO ALL) ---
st.header("🔪 Current Kitchen Brigades")
col1, col2, col3 = st.columns(3)

def display_team(team_name):
    st.markdown("##### 👨‍🍳 Chefs")
    response = supabase.table("players").select("*").eq("team", team_name).execute()
    team_players = response.data
    
    if not team_players: 
        st.write("*No chefs drafted yet.*")
        
    for p in team_players:
        with st.container(border=True): 
            st.markdown(f"**{p['name']}**")
            roster_col1, roster_col2 = st.columns([1, 2])
            with roster_col1:
                if p["image_data"]: 
                    st.image(p["image_data"], width=60)
            with roster_col2:
                attr_dict = json.loads(p["attributes"])
                for k, v in attr_dict.items(): 
                    st.write(f"- {k}: {v}")
                    
    st.markdown("##### 🍽️ Assigned Meals")
    response = supabase.table("meals").select("meal_name").eq("team", team_name).execute()
    team_meals = response.data
    
    if not team_meals: 
        st.write("*No meals assigned yet.*")
    else:
        for m in team_meals: 
            st.write(f"- {m['meal_name']}")

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
            
            response = supabase.table("players").select("name, team").neq("team", "None").execute()
            drafted_players = response.data
            
            if len(drafted_players) > 0:
                undo_options = [f"{p['name']} (Current: {p['team']})" for p in drafted_players]
                selected_undo = st.selectbox("Return a CHEF to the pool:", undo_options)
                if st.button("Undo Chef Assignment"):
                    name_to_undo = selected_undo.split(" (Current:")[0]
                    supabase.table("players").update({"team": "None"}).eq("name", name_to_undo).execute()
                    log_action(f"UNDO: Chef {name_to_undo} was returned to the pool.")
                    st.rerun()
            st.write("---")
            
            response = supabase.table("meals").select("meal_name, team").neq("team", "None").execute()
            assigned_meals = response.data
            
            if len(assigned_meals) > 0:
                meal_undo_options = [f"{m['meal_name']} (Current: {m['team']})" for m in assigned_meals]
                selected_meal_undo = st.selectbox("Return a MEAL to the pool:", meal_undo_options)
                if st.button("Undo Meal Assignment"):
                    meal_to_undo = selected_meal_undo.split(" (Current:")[0]
                    supabase.table("meals").update({"team": "None"}).eq("meal_name", meal_to_undo).execute()
                    log_action(f"UNDO: Meal '{meal_to_undo}' was returned to the pool.")
                    st.rerun()
                    
        with admin_col2:
            st.subheader("Action Log")
            # Fetch the latest 20 logs
            response = supabase.table("action_log").select("timestamp, log_text").order("id", desc=True).limit(20).execute()
            logs = response.data
            
            if not logs: 
                st.write("No actions taken yet.")
            else:
                log_display = "".join([f"[{log['timestamp'].split('T')[0]}] {log['log_text']}\n" for log in logs])
                st.code(log_display, language="text")
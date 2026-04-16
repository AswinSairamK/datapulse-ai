# ============================================================
# DataPulse AI — Streamlit Dashboard (with JWT Authentication)
# ============================================================
# Multi-user dashboard with login/signup
# - Users must log in to access the dashboard
# - Token is stored in session state
# - All API calls include the token
# - Each user sees only their own data
# ============================================================

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- Config ---
API_BASE = "http://localhost:8000/api"

st.set_page_config(
    page_title="DataPulse AI",
    page_icon="🔍",
    layout="wide"
)

# ============================================================
# Session state initialization
# ============================================================
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None


# ============================================================
# Helper Functions (with auth headers)
# ============================================================
def get_headers():
    """Get auth headers with JWT token."""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def api_get(endpoint):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", headers=get_headers(), timeout=30)
        if r.status_code == 401:
            st.session_state.token = None
            st.session_state.user = None
            st.error("Session expired. Please log in again.")
            st.rerun()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint, data=None):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data, headers=get_headers(), timeout=60)
        if r.status_code == 401:
            st.session_state.token = None
            st.session_state.user = None
            st.error("Session expired. Please log in again.")
            st.rerun()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_delete(endpoint):
    try:
        r = requests.delete(f"{API_BASE}{endpoint}", headers=get_headers(), timeout=10)
        if r.status_code == 401:
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def login(username, password):
    """Login to the API — uses OAuth2 form data (not JSON)."""
    try:
        r = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": username, "password": password},  # Form data, not JSON
            timeout=10
        )
        if r.status_code == 200:
            result = r.json()
            st.session_state.token = result["access_token"]
            st.session_state.user = result["user"]
            return True, "Login successful"
        else:
            error = r.json().get("detail", "Login failed")
            return False, error
    except Exception as e:
        return False, str(e)


def signup(email, username, password):
    """Sign up a new user."""
    try:
        r = requests.post(
            f"{API_BASE}/auth/signup",
            json={"email": email, "username": username, "password": password},
            timeout=10
        )
        if r.status_code == 200:
            result = r.json()
            st.session_state.token = result["access_token"]
            st.session_state.user = result["user"]
            return True, "Signup successful"
        else:
            error = r.json().get("detail", "Signup failed")
            return False, error
    except Exception as e:
        return False, str(e)


def logout():
    st.session_state.token = None
    st.session_state.user = None
    st.rerun()


# ============================================================
# LOGIN / SIGNUP SCREEN
# ============================================================
if not st.session_state.token:
    st.title("🔍 DataPulse AI")
    st.markdown("**Intelligent Data Quality Monitoring & AI-Powered Analytics**")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        tab_login, tab_signup = st.tabs(["🔐 Login", "✨ Sign Up"])

        with tab_login:
            st.markdown("### Welcome back")
            with st.form("login_form"):
                login_username = st.text_input("Email or Username", placeholder="aswin@example.com")
                login_password = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Login", type="primary", use_container_width=True)

                if login_submit:
                    if login_username and login_password:
                        success, msg = login(login_username, login_password)
                        if success:
                            st.success("Logging in...")
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Please enter both username and password")

        with tab_signup:
            st.markdown("### Create account")
            with st.form("signup_form"):
                signup_email = st.text_input("Email", placeholder="aswin@example.com")
                signup_username = st.text_input("Username", placeholder="aswin")
                signup_password = st.text_input("Password (min 8 characters)", type="password")
                signup_submit = st.form_submit_button("Sign Up", type="primary", use_container_width=True)

                if signup_submit:
                    if signup_email and signup_username and signup_password:
                        if len(signup_password) < 8:
                            st.error("Password must be at least 8 characters")
                        else:
                            success, msg = signup(signup_email, signup_username, signup_password)
                            if success:
                                st.success("Account created! Redirecting...")
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.warning("Please fill all fields")

    st.stop()  # Don't show the rest of the app if not logged in


# ============================================================
# MAIN APP (authenticated)
# ============================================================
user = st.session_state.user

# Header with logout button
col_title, col_user = st.columns([5, 1])
with col_title:
    st.title("🔍 DataPulse AI")
    st.markdown("**Intelligent Data Quality Monitoring & AI-Powered Analytics**")
with col_user:
    st.markdown(f"**👤 {user['username']}**")
    st.caption(user["email"])
    if st.button("Logout", use_container_width=True):
        logout()

st.markdown("---")

# --- Sidebar: Data Source Selection ---
with st.sidebar:
    st.header("Data Sources")

    sources = api_get("/data-sources")

    if sources and isinstance(sources, list) and len(sources) > 0:
        source_names = {s["name"]: s["id"] for s in sources}
        selected_name = st.selectbox("Select database", list(source_names.keys()))
        selected_id = source_names[selected_name]
        st.success(f"Connected to: {selected_name}")
    else:
        selected_id = None
        st.warning("No data sources connected")

    st.markdown("---")
    st.subheader("Add new connection")

    with st.form("add_source"):
        new_name = st.text_input("Name", placeholder="My Database")
        new_type = st.selectbox("Database type", ["postgresql", "mysql", "snowflake"])
        new_host = st.text_input("Host / Account", value="localhost")
        new_port = st.text_input("Port / Warehouse", value="5432")
        new_db = st.text_input("Database / Schema", placeholder="ecommerce_db")
        new_user = st.text_input("Username", value="postgres")
        new_pass = st.text_input("Password", type="password")
        submit = st.form_submit_button("Connect")

        if submit and new_name and new_db:
            result = api_post("/data-sources", {
                "name": new_name,
                "host": new_host,
                "port": new_port,
                "database_name": new_db,
                "username": new_user,
                "password": new_pass,
                "db_type": new_type
            })
            if result and "id" in result:
                st.success("Connected successfully!")
                st.rerun()
            elif result and "detail" in result:
                st.error(result["detail"])


# --- Main Content: Tabs ---
if selected_id:
    tab_chat, tab_health, tab_rules, tab_suggest = st.tabs(
        ["💬 Chat with Data", "📊 Health Monitor", "⚙️ Rules", "🤖 AI Suggest"]
    )

    # ============================================================
    # TAB 1: Chat with Data
    # ============================================================
    with tab_chat:
        st.subheader("💬 Chat with your database")
        st.markdown("Ask questions in plain English — AI writes the SQL and explains the results.")

        user_question = st.text_input(
            "Ask a question about your data:",
            placeholder="e.g., Which are the top 5 countries by revenue?"
        )

        col_send, col_examples = st.columns([1, 3])
        with col_send:
            send_clicked = st.button("Send", type="primary", use_container_width=True)

        with col_examples:
            st.markdown("**Try:** *How many records?* · *Monthly revenue trend* · *Top products*")

        if send_clicked and user_question:
            with st.spinner("AI is thinking..."):
                result = api_post("/chat", {
                    "data_source_id": selected_id,
                    "message": user_question
                })

            if result:
                st.markdown("### Answer")
                st.markdown(result.get("ai_response", "No response"))

                # Auto-visualization
                chart_config = result.get("chart_config") or {}
                chart_type = chart_config.get("chart_type", "table")
                rows = result.get("rows") or []
                columns = result.get("columns") or []

                if rows and columns and chart_type != "table":
                    st.markdown("### 📊 Visualization")
                    chart_df = pd.DataFrame(rows, columns=columns)

                    x_col = chart_config.get("x_column")
                    y_col = chart_config.get("y_column")
                    title = chart_config.get("title", "Query Results")

                    try:
                        chart_df[y_col] = pd.to_numeric(chart_df[y_col], errors="coerce")

                        if chart_type == "bar":
                            fig = px.bar(chart_df, x=x_col, y=y_col, title=title)
                        elif chart_type == "line":
                            fig = px.line(chart_df, x=x_col, y=y_col, title=title, markers=True)
                        elif chart_type == "pie":
                            fig = px.pie(chart_df, names=x_col, values=y_col, title=title)
                        elif chart_type == "scatter":
                            fig = px.scatter(chart_df, x=x_col, y=y_col, title=title)
                        else:
                            fig = None

                        if fig:
                            fig.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20))
                            st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render chart: {e}")

                if rows and columns:
                    st.markdown("### 📋 Data")
                    data_df = pd.DataFrame(rows, columns=columns)
                    st.dataframe(data_df, use_container_width=True, hide_index=True)

                with st.expander("View generated SQL"):
                    st.code(result.get("generated_sql", "N/A"), language="sql")

                if result.get("query_success"):
                    st.success("Query executed successfully")
                else:
                    st.error("Query failed")

    # ============================================================
    # TAB 2: Health Monitor
    # ============================================================
    with tab_health:
        st.subheader("📊 Data Quality Health Monitor")

        col_run, col_spacer = st.columns([1, 3])
        with col_run:
            run_clicked = st.button("🔄 Run checks now", type="primary", use_container_width=True)

        if run_clicked:
            with st.spinner("Running data quality checks..."):
                results = api_post(f"/checks/run/{selected_id}")

            if results and "overall_score" in results:
                score = results["overall_score"]
                total = results["total_rules"]
                passed = results["passed"]
                failed = results["failed"]

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Overall Score", f"{score}/100")
                c2.metric("Total Checks", total)
                c3.metric("Passed", passed)
                c4.metric("Failed", failed)

                st.markdown("---")

                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=score,
                    title={"text": "Data Health Score"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "#4ECDC4" if score >= 80 else "#FFD93D" if score >= 50 else "#FF6B6B"},
                        "steps": [
                            {"range": [0, 50], "color": "#FCEBEB"},
                            {"range": [50, 80], "color": "#FAEEDA"},
                            {"range": [80, 100], "color": "#EAF3DE"},
                        ],
                    }
                ))
                fig_gauge.update_layout(height=300)
                st.plotly_chart(fig_gauge, use_container_width=True)

                st.markdown("### Check results")
                for r in results["results"]:
                    status = "✅" if r["passed"] else "❌"
                    severity_color = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(r["severity"], "⚪")

                    with st.expander(f"{status} {severity_color} {r['table']}.{r['column']} — {r['check_type']}"):
                        col_a, col_b = st.columns(2)
                        col_a.markdown(f"**Expected:** {r['expected_value']}")
                        col_b.markdown(f"**Actual:** {r['actual_value']}")
                        st.markdown(f"**Message:** {r['message']}")
                        st.markdown(f"**Score:** {round(r['score'], 1)}/100")
            elif results and "message" in results:
                st.info(results["message"])

    # ============================================================
    # TAB 3: Rules Management
    # ============================================================
    with tab_rules:
        st.subheader("⚙️ Monitoring Rules")

        tables_data = api_get(f"/data-sources/{selected_id}/tables")
        table_names = []
        if tables_data and "tables" in tables_data:
            table_names = [t["table_name"] for t in tables_data["tables"] if "error" not in t]

        st.markdown("### Add new rule")
        with st.form("add_rule"):
            col1, col2 = st.columns(2)

            with col1:
                rule_table = st.selectbox("Table", table_names if table_names else ["No tables found"])
                if rule_table and rule_table != "No tables found":
                    cols_data = api_get(f"/data-sources/{selected_id}/tables/{rule_table}/columns")
                    col_names = [c["column_name"] for c in cols_data.get("columns", []) if "error" not in c] if cols_data else []
                else:
                    col_names = []
                rule_column = st.selectbox("Column", col_names if col_names else ["Select a table first"])

            with col2:
                rule_type = st.selectbox("Check type", [
                    "null_check", "range_check", "duplicate_check", "freshness_check", "custom_sql"
                ])
                rule_severity = st.selectbox("Severity", ["critical", "warning", "info"])

            col3, col4 = st.columns(2)
            with col3:
                rule_min = st.text_input("Min value (for range check)", value="")
            with col4:
                rule_max = st.text_input("Max value / threshold", value="")

            rule_sql = st.text_area("Custom SQL (for custom_sql type only)", value="")

            add_rule = st.form_submit_button("Add Rule", type="primary")

            if add_rule:
                rule_data = {
                    "data_source_id": selected_id,
                    "table_name": rule_table,
                    "column_name": rule_column,
                    "check_type": rule_type,
                    "min_value": rule_min if rule_min else None,
                    "max_value": rule_max if rule_max else None,
                    "custom_sql": rule_sql if rule_sql else None,
                    "severity": rule_severity
                }
                result = api_post("/rules", rule_data)
                if result and "id" in result:
                    st.success(f"Rule added! (ID: {result['id']})")
                    st.rerun()

        st.markdown("---")
        st.markdown("### Active rules")
        rules = api_get(f"/rules/{selected_id}")

        if isinstance(rules, dict):
            if "detail" in rules:
                st.error(f"Error loading rules: {rules['detail']}")
                rules = []
            else:
                rules = []

        if rules and len(rules) > 0:
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                col_info, col_delete = st.columns([5, 1])
                with col_info:
                    st.markdown(
                        f"**{rule['check_type']}** on `{rule['table_name']}.{rule.get('column_name', '*')}` "
                        f"| Severity: {rule['severity']}"
                    )
                with col_delete:
                    if st.button("🗑️", key=f"del_{rule['id']}"):
                        api_delete(f"/rules/{rule['id']}")
                        st.rerun()
        else:
            st.info("No rules configured.")

    # ============================================================
    # TAB 4: AI Suggest
    # ============================================================
    with tab_suggest:
        st.subheader("🤖 AI-Powered Rule Suggestions")

        if table_names:
            suggest_table = st.selectbox("Select table to analyze", table_names, key="suggest_table")

            if st.button("🧠 Analyze and suggest rules", type="primary"):
                with st.spinner("AI is profiling your table..."):
                    result = api_get(f"/suggest/{selected_id}/{suggest_table}")

                if result and "suggestions" in result:
                    suggestions = result["suggestions"]

                    if len(suggestions) > 0 and "error" not in suggestions[0]:
                        st.success(f"AI suggested {len(suggestions)} rules")

                        for i, s in enumerate(suggestions):
                            with st.expander(
                                f"{s.get('check_type', 'unknown')} on {s.get('column_name', '*')} — {s.get('severity', 'info')}"
                            ):
                                st.markdown(f"**Reason:** {s.get('reason', 'No reason')}")
                                if st.button(f"Accept", key=f"accept_{i}"):
                                    accept_data = {
                                        "data_source_id": selected_id,
                                        "table_name": suggest_table,
                                        "column_name": s.get("column_name"),
                                        "check_type": s.get("check_type"),
                                        "min_value": s.get("min_value"),
                                        "max_value": str(s.get("max_value")) if s.get("max_value") else None,
                                        "severity": s.get("severity", "warning")
                                    }
                                    res = api_post("/rules", accept_data)
                                    if res and "id" in res:
                                        st.success(f"Rule accepted!")
        else:
            st.info("No tables found.")

else:
    st.info("👈 Connect a database using the sidebar to get started.")

st.markdown("---")
st.markdown(f"**DataPulse AI** v1.0 | Logged in as: `{user['username']}`")
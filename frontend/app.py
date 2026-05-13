from __future__ import annotations

import os
import uuid

import requests
import streamlit as st
from components.file_card import render_file_card
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DEMO_USERS = {
    "Demo User": "demo-user",
    "Recruiter Demo": "recruiter-demo",
    "Founder Demo": "founder-demo",
}

st.set_page_config(
    page_title="Drive Search",
    page_icon="🗂️",
    layout="wide",
)

st.markdown(
    """
<style>

    @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap');

    /* Apply the font to the entire Streamlit app */
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Instrument Serif', serif;
    }

    /* Hide default header/footer */
    #MainMenu {visibility: hidden;}
    footer    {visibility: hidden;}
    header    {visibility: hidden;}

    /* Main app background (the white edges) */
    [data-testid="stAppViewContainer"] {
        background-color: #FFFFFF;
    }

    /* The gray "floating" main content area */
    [data-testid="stAppViewBlockContainer"] {
        background-color: #F7F7F8;
        border-radius: 24px;
        margin-top: 2rem;
        margin-bottom: 2rem;
        padding: 2rem;
        border: 1px solid #E5E5E5;
        max-width: 1200px;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #F7F7F8 !important;
        border-right: none;
    }

    /* Style User Chat Messages (Right aligned, gray pill) */
    [data-testid="stChatMessage"][data-baseweb="block"]:has(div:contains("user")) {
        background-color: #ECECEC;
        border-radius: 10px;
        padding: 10px 20px;
        margin-left: auto;
        max-width: 70%;
    }

    /* Style Assistant Chat Messages (Left aligned, transparent) */
    [data-testid="stChatMessage"][data-baseweb="block"]:has(div:contains("assistant")) {
        background-color: transparent;
        padding: 10px 20px;
        max-width: 80%;
    }

    /* Hide default chat avatars to match the clean look */
    [data-testid="chatAvatarIcon-user"], [data-testid="chatAvatarIcon-assistant"] {
        display: none;
    }

    /* Style the Chat Input Container to look floating */
    [data-testid="stChatInput"] {
        border-radius: 20px;
        border: 1px solid #E5E5E5;
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.05);
        background-color: #FFFFFF;
        padding: 0.5rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


if "user_id" not in st.query_params:
    st.query_params["user_id"] = DEMO_USERS["Demo User"]
user_id: str = st.query_params["user_id"]


if "sessions" not in st.session_state:
    st.session_state.sessions = []
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "sessions_loaded" not in st.session_state:
    st.session_state.sessions_loaded = False
if "backend_online" not in st.session_state:
    st.session_state.backend_online = True


def api(method: str, path: str, **kwargs):
    """Returns parsed JSON on success, None on any error."""
    try:
        r = getattr(requests, method)(f"{BACKEND_URL}{path}", timeout=60, **kwargs)
        r.raise_for_status()
        st.session_state.backend_online = True
        return r.json()
    except requests.exceptions.ConnectionError:
        st.session_state.backend_online = False
        return None
    except requests.exceptions.HTTPError as exc:
        try:
            detail = r.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        st.warning(f"Backend error ({path}): {detail}")
        return None
    except Exception as exc:
        st.warning(f"Backend error ({path}): {exc}")
        return None


def load_sessions() -> list[dict]:
    return api("get", f"/users/{user_id}/sessions") or []


def load_profile() -> dict:
    return api("get", f"/users/{user_id}/profile") or {
        "user_id": user_id,
        "session_count": len(st.session_state.sessions),
        "memory_count": 0,
    }


def load_history(session_id: str) -> list[dict]:
    data = api("get", f"/sessions/{session_id}/history")
    return data.get("messages", []) if data else []


def create_session(title: str = "New Chat") -> dict | None:
    return api("post", f"/users/{user_id}/sessions", json={"title": title})


def rename_session(session_id: str, title: str) -> None:
    api("patch", f"/sessions/{session_id}/title", json={"title": title})


def delete_session_api(session_id: str) -> None:
    api("delete", f"/sessions/{session_id}")


def extract_memory(session_id: str | None) -> None:
    if session_id:
        api("post", f"/sessions/{session_id}/extract-memory", json={"user_id": user_id})


# On first render: load sessions, restore last active, or auto-create one
if not st.session_state.sessions_loaded:
    st.session_state.sessions = load_sessions()
    st.session_state.sessions_loaded = True

    if st.session_state.sessions:
        # returning user — restore the most recent session
        latest = st.session_state.sessions[0]
        st.session_state.active_session_id = latest["session_id"]
        st.session_state.messages = load_history(latest["session_id"])
    elif st.session_state.backend_online:
        # first ever visit — silently create a default session so chat is ready
        sess = create_session("New Chat")
        if sess:
            st.session_state.sessions = [sess]
            st.session_state.active_session_id = sess["session_id"]
            st.session_state.messages = []


# actions
def switch_to(session_id: str) -> None:
    if session_id != st.session_state.active_session_id:
        extract_memory(st.session_state.active_session_id)
    st.session_state.active_session_id = session_id
    st.session_state.messages = load_history(session_id)


def new_chat() -> None:
    extract_memory(st.session_state.active_session_id)
    sess = create_session("New Chat")
    if sess:
        st.session_state.sessions.insert(0, sess)
        st.session_state.active_session_id = sess["session_id"]
        st.session_state.messages = []


def remove_session(session_id: str) -> None:
    delete_session_api(session_id)
    st.session_state.sessions = [
        s for s in st.session_state.sessions if s["session_id"] != session_id
    ]
    if st.session_state.active_session_id == session_id:
        # switch to the next available session, or clear
        remaining = st.session_state.sessions
        if remaining:
            switch_to(remaining[0]["session_id"])
        else:
            st.session_state.active_session_id = None
            st.session_state.messages = []


def switch_user(next_user_id: str) -> None:
    extract_memory(st.session_state.active_session_id)
    st.query_params["user_id"] = next_user_id
    st.session_state.sessions = []
    st.session_state.active_session_id = None
    st.session_state.messages = []
    st.session_state.sessions_loaded = False
    st.rerun()

# sidebar
with st.sidebar:
    st.markdown("### 🗂️ TailorTalk")

    profile_labels = list(DEMO_USERS.keys())
    current_label = next(
        (label for label, uid in DEMO_USERS.items() if uid == user_id),
        "Custom",
    )
    select_options = profile_labels + (["Custom"] if current_label == "Custom" else [])
    selected_label = st.selectbox(
        "Profile",
        select_options,
        index=select_options.index(current_label),
    )

    if selected_label != "Custom" and DEMO_USERS[selected_label] != user_id:
        switch_user(DEMO_USERS[selected_label])

    profile = load_profile()
    st.caption(
        f"{profile.get('session_count', 0)} sessions | "
        f"{profile.get('memory_count', 0)} memories"
    )

    with st.expander("Advanced"):
        custom_user_id = st.text_input("Custom user ID", value=user_id)
        if st.button("Switch profile", use_container_width=True):
            next_user_id = custom_user_id.strip() or str(uuid.uuid4())
            if next_user_id != user_id:
                switch_user(next_user_id)
        st.caption(f"Current scope: `{user_id}`")

    st.divider()

    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        new_chat()
        st.rerun()

    st.markdown("**Sessions**")

    for sess in st.session_state.sessions:
        sid = sess["session_id"]
        title = sess.get("title", "Untitled")[:32]
        active = sid == st.session_state.active_session_id

        col_btn, col_del = st.columns([5, 1])
        with col_btn:
            label = f"**▶ {title}**" if active else title
            if st.button(label, key=f"s_{sid}", use_container_width=True):
                switch_to(sid)
                st.rerun()
        with col_del:
            if st.button("🗑", key=f"d_{sid}", help="Delete this session"):
                remove_session(sid)
                st.rerun()


# Main Talk Area
st.markdown("## 🗂️ Drive Lens")

# Backend offline banner — shown instead of a cryptic warning
if not st.session_state.backend_online:
    st.error(
        "⚠️ Cannot reach the backend at **localhost:8000**. "
        "Run `uvicorn backend.main:app --reload` from the project root, then refresh."
    )
    st.stop()

st.caption("Ask me to find any file in natural language.")
st.divider()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("files"):
            for f in msg["files"]:
                render_file_card(f)
        if msg.get("drive_query"):
            with st.expander("🔍 Drive query used"):
                st.code(msg["drive_query"])
        if msg.get("latency_ms"):
            st.caption(f"⚡ {msg['latency_ms']} ms")


# inpur
if prompt := st.chat_input("e.g. Find all PDFs modified last month..."):
    if not st.session_state.active_session_id:
        sess = create_session(prompt[:40])
        if not sess:
            st.error("Backend is not available. Please start it first.")
            st.stop()
        st.session_state.sessions.insert(0, sess)
        st.session_state.active_session_id = sess["session_id"]
        st.session_state.messages = []

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching Drive..."):
            resp = api(
                "post",
                "/chat",
                json={
                    "session_id": st.session_state.active_session_id,
                    "user_id": user_id,
                    "message": prompt,
                },
            )

        if resp is None:
            st.error("Backend did not respond. Check the backend terminal for errors.")
            st.stop()

        st.markdown(resp["reply"])

        for f in resp.get("files", []):
            render_file_card(f)

        if resp.get("drive_query"):
            with st.expander("🔍 Drive query used"):
                st.code(resp["drive_query"])

        st.caption(f"⚡ {resp.get('latency_ms', '?')} ms")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": resp["reply"],
            "files": resp.get("files", []),
            "drive_query": resp.get("drive_query"),
            "latency_ms": resp.get("latency_ms"),
        }
    )

    active_sess = next(
        (
            s
            for s in st.session_state.sessions
            if s["session_id"] == st.session_state.active_session_id
        ),
        None,
    )
    if active_sess and active_sess.get("title") in ("New Chat", ""):
        new_title = prompt[:40] + ("..." if len(prompt) > 40 else "")
        rename_session(st.session_state.active_session_id, new_title)
        active_sess["title"] = new_title

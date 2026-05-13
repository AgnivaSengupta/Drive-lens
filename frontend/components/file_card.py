from html import escape

import streamlit as st

MIME_ICONS = {
    "application/pdf": "📄",
    "application/vnd.google-apps.spreadsheet": "📊",
    "application/vnd.google-apps.document": "📝",
    "application/vnd.google-apps.presentation": "📑",
    "image/jpeg": "🖼️",
    "image/png": "🖼️",
}


def render_file_card(file: dict):
    icon = MIME_ICONS.get(file["mimeType"], "📁")
    name = escape(file["name"])
    link = escape(file.get("webViewLink") or "#", quote=True)
    modified = escape((file.get("modifiedTime") or "")[:10])

    st.markdown(
        f"""
    <div style="
        background:#f5f4f2 hover:#d4d3d2;
        border:1px solid #bfbfbd;
        border-radius:10px;
        padding:10px 14px;
        margin-bottom:10px;
        transition: border 0.2s;
        display: flex;
        align-items: center;
    ">
        <span style="font-size:1.4rem">{icon}</span>
        <div>
        <a href="{link}" target="_blank" style="
            color:#6C63FF;
            font-weight:600;
            font-size:1rem;
            text-decoration:none;
            margin-left:10px;
        ">{name}</a>
        <div style="color:#888; font-size:0.8rem; margin-top:4px; margin-left:10px">
            Modified: {modified}
        </div>
        <div>
    </div>
    """,
        unsafe_allow_html=True,
    )

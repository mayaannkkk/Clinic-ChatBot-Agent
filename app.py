import streamlit as st
from datetime import datetime, time
from graph import graph
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import pandas as pd
import re

st.set_page_config(page_title="Clinic Chatbot", page_icon="💬")
st.title("💬 Clinic Chatbot")
st.header("Hello, Welcome to the Clinic Chatbot 😊")

# ---- Define allowed times (clinic hours) ----
def get_allowed_times():
    allowed = []
    for h in range(8, 12):
        for m in [0, 15, 30, 45]:
            if h == 11 and m > 45:
                continue
            allowed.append(time(h, m))
    for h in range(16, 22):
        for m in [0, 15, 30, 45]:
            if h == 21 and m > 45:
                continue
            allowed.append(time(h, m))
    return allowed

ALLOWED_TIMES = get_allowed_times()

# ---- Validate date/time ----
def validate_datetime(date_time_str: str) -> tuple[bool, str]:
    try:
        dt = pd.to_datetime(date_time_str)
        if not (8 <= dt.hour < 12 or 16 <= dt.hour < 22):
            return False, f"⚠️ {date_time_str} is outside clinic hours (8-12 AM, 4-10 PM)."
        if dt < datetime.now():
            return False, f"⚠️ {date_time_str} is in the past. Please choose a future date."
        return True, "Valid"
    except Exception:
        return False, "⚠️ Invalid date/time format. Please use the calendar picker."

def looks_like_date_time(text):
    patterns = [
        r'\d{4}-\d{2}-\d{2}.*\d{1,2}:\d{2}',
        r'\d{2}/\d{2}/\d{4}.*\d{1,2}:\d{2}',
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False

def send_to_graph(user_text: str):
    st.session_state.graph_state["messages"].append(HumanMessage(content=user_text))
    result = graph.invoke(st.session_state.graph_state)
    st.session_state.graph_state = result

    assistant_content = None
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            assistant_content = msg.content
            break
        elif isinstance(msg, ToolMessage):
            continue

    if assistant_content is None:
        assistant_content = "I'm processing your request. Please wait."

    st.session_state.messages.append({"role": "assistant", "content": assistant_content})
    with st.chat_message("assistant"):
        st.markdown(assistant_content)

# ---- Initialize session state ----
if "messages" not in st.session_state:
    st.session_state.messages = []
if "graph_state" not in st.session_state:
    st.session_state.graph_state = {"messages": []}
    greeting = "Hello! Welcome to the Clinic Chatbot. Would you like to book an appointment or check a walk-in time?"
    st.session_state.graph_state["messages"].append(AIMessage(content=greeting))
    st.session_state.messages.append({"role": "assistant", "content": greeting})

# ---- Display chat history ----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---- Calendar: show when assistant asks for it, OR after a validation error ----
show_calendar = False

if st.session_state.messages:
    last_msg = st.session_state.messages[-1]

    # Show calendar if the user just sent a date/time (so they can correct)
    if last_msg["role"] == "user" and looks_like_date_time(last_msg["content"]):
        show_calendar = True
    else:
        # Check last assistant message for trigger phrases
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "assistant":
                content = msg["content"].lower()
                # Show calendar if assistant asks for it, OR if it contains an error about date/time
                if ("using the calendar below" in content or 
                    "past" in content or 
                    "future" in content or 
                    "invalid" in content or 
                    "outside clinic hours" in content or
                    "choose a valid date" in content):
                    show_calendar = True
                break

# ---- Calendar and Time Picker ----
if show_calendar:
    with st.container():
        st.markdown("---")
        st.markdown("### 📅 Select Date and Time")
        col1, col2 = st.columns(2)
        with col1:
            selected_date = st.date_input("Date", min_value=datetime.today().date())
        with col2:
            selected_time = st.selectbox(
                "Time",
                ALLOWED_TIMES,
                format_func=lambda t: t.strftime("%I:%M %p"),
                index=0
            )

        if st.button("📤 Send Selected Date & Time", type="primary", use_container_width=True):
            date_time_str = f"{selected_date.strftime('%Y-%m-%d')} {selected_time.strftime('%I:%M %p').lstrip('0')}"

            is_valid, message = validate_datetime(date_time_str)

            st.session_state.messages.append({"role": "user", "content": date_time_str})
            with st.chat_message("user"):
                st.markdown(date_time_str)

            if not is_valid:
                st.session_state.messages.append({"role": "assistant", "content": message})
                with st.chat_message("assistant"):
                    st.markdown(message)
            else:
                send_to_graph(date_time_str)

            st.rerun()

# ---- Chat Input ----
if prompt := st.chat_input("Type your message here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # If typed text looks like a date/time, validate it first
    if looks_like_date_time(prompt):
        is_valid, message = validate_datetime(prompt)
        if not is_valid:
            st.session_state.messages.append({"role": "assistant", "content": message})
            with st.chat_message("assistant"):
                st.markdown(message)
            st.rerun()

    send_to_graph(prompt)
    st.rerun()
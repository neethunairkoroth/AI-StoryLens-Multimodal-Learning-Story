import os
import json
import re
import tempfile
import time
import requests
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Gemini Setup
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Audio Setup
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="StoryLens | Cinematic AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------- PREMIUM CINEMATIC CSS ----------
def inject_ui():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400..900;1,400..900&family=Inter:wght@300;400;600&display=swap');

    :root {
        --gold: #D1B000;
        --soft-gold: #FFD700;
        --bg: #080808;
        --card: rgba(25, 25, 25, 0.7);
    }

    .stApp {
        background-color: var(--bg);
        color: #E0E0E0;
    }

    h1, h2, h3 {
        font-family: 'Playfair Display', serif;
        color: var(--gold) !important;
        letter-spacing: 1px;
    }

    /* Glass Effect Cards */
    .scene-container {
        background: var(--card);
        border: 1px solid rgba(209, 176, 0, 0.2);
        padding: 40px;
        border-radius: 25px;
        margin-bottom: 50px;
        backdrop-filter: blur(10px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.4);
        transition: all 0.3s ease;
    }
    
    .scene-container:hover {
        border-color: var(--gold);
        transform: translateY(-5px);
    }

    .scene-meta {
        font-family: 'Inter', sans-serif;
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 4px;
        color: var(--gold);
        margin-bottom: 15px;
        opacity: 0.8;
    }

    .narration-script {
        background: rgba(40, 40, 40, 0.5);
        padding: 20px;
        border-radius: 12px;
        border-left: 4px solid var(--gold);
        font-style: italic;
        color: #CCC;
        margin: 20px 0;
    }

    /* Cinematic Generate Button */
    div.stButton > button {
        background: linear-gradient(135deg, #D1B000 0%, #8A7300 100%);
        color: black !important;
        border: none;
        padding: 20px 50px;
        border-radius: 60px;
        font-weight: 700;
        font-size: 1.1rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        width: 100%;
        box-shadow: 0 10px 30px rgba(209, 176, 0, 0.3);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }

    div.stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 15px 40px rgba(209, 176, 0, 0.5);
        filter: brightness(1.2);
    }

    /* Media Styling */
    .stImage > img {
        border-radius: 15px;
        border: 1px solid rgba(255,255,255,0.1);
    }

    </style>
    """, unsafe_allow_html=True)

inject_ui()

# ---------- CORE LOGIC ----------

def get_api_key():
    # Priority: Manual Sidebar Input > Env Var
    manual_key = st.session_state.get("manual_key", "").strip()
    if manual_key:
        return manual_key
    return os.getenv("GEMINI_API_KEY", "").strip()

def generate_story(topic, style, tone, model_name):
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Missing Gemini API Key. Set 'GEMINI_API_KEY' in .env or Sidebar.")
    
    if not GENAI_AVAILABLE:
        raise ImportError("google-generativeai library is not installed.")

    genai.configure(api_key=api_key)
    
    # Extensive fallback sequence to bypass regional/plan limits
    # Removing 'gemini-pro' as it often causes 404, using 1.0-pro instead
    fallbacks = [
        model_name, 
        "gemini-2.0-flash", 
        "gemini-1.5-flash", 
        "gemini-1.5-flash-latest", 
        "gemini-1.5-pro", 
        "gemini-1.5-pro-latest",
        "gemini-1.0-pro"
    ]
    last_error = None

    for m in fallbacks:
        try:
            model = genai.GenerativeModel(m)
            prompt = f"""
            Acting as a Hollywood creative director, script a 3-scene educational story about: {topic}.
            Style: {style} | Tone: {tone}.

            Return ONLY a JSON response:
            {{
              "title": "Compelling Title",
              "hook": "Magnetic opening sentence",
              "scenes": [
                {{
                  "id": 1,
                  "title": "Scene Focus",
                  "content": "Short educational explanation",
                  "visual": "Very detailed cinematic image prompt (atmospheric, lighting, composition)",
                  "voice": "Narrator script"
                }},
                ... (3 scenes)
              ]
            }}
            """
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            return json.loads(response.text)
        except Exception as e:
            last_error = e
            # Log the attempt for debugging in terminal
            print(f"Attempt with {m} failed: {e}")
            
            error_msg = str(e).lower()
            if "404" in error_msg or "not found" in error_msg or "429" in error_msg or "quota" in error_msg:
                continue # Try next fallback model
            else:
                raise e # Real error (auth, etc)
    
    if "429" in str(last_error) or "quota" in str(last_error).lower():
        raise Exception("Gemini API Quota Exceeded. Please wait a minute or use another API key.")
    raise last_error # If all fail

def get_cinematic_image(prompt):
    # Free Cinematic Image Gen (Pollinations AI)
    encoded = requests.utils.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true&seed={time.time()}"

def generate_audio(text, scene_id):
    if not GTTS_AVAILABLE: return None
    temp_dir = Path(tempfile.gettempdir()) / "storylens"
    temp_dir.mkdir(parents=True, exist_ok=True)
    path = temp_dir / f"audio_{scene_id}.mp3"
    gTTS(text=text, lang='en').save(str(path))
    return str(path)

# ---------- HEADER ----------
st.markdown("<h1 style='font-size: 5rem; text-align: center; margin-bottom:0;'>STORYLENS</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; opacity: 0.5; letter-spacing: 8px; font-weight: 300;'>AI PRODUCTION STUDIO</p>", unsafe_allow_html=True)

# ---------- SIDEBAR / SETTINGS ----------
with st.sidebar:
    st.markdown("### 🛠️ Production Settings")
    if not os.getenv("GEMINI_API_KEY"):
        st.session_state["manual_key"] = st.text_input("Enter API Key", type="password")
    
    style_choice = st.selectbox("Cinematic Style", ["Vintage Noir", "Hyper-Realistic", "3D Pixar Style", "Cyberpunk", "Classic Oil Painting"])
    tone_choice = st.selectbox("Narrative Tone", ["Epic", "Inspiring", "Mysterious", "Educational", "Playful"])
    
    st.divider()
    st.markdown("### 🔑 API Key Override")
    st.session_state["manual_key"] = st.text_input("New API Key (Overrides .env)", type="password")
    if st.button("Clear Cache & Reload"):
        st.session_state.clear()
        st.rerun()

    st.divider()
    st.markdown("### 🤖 Model Engine")
    model_options = [
        "gemini-2.0-flash", 
        "gemini-1.5-flash", 
        "gemini-1.5-flash-latest", 
        "gemini-1.5-pro",
        "gemini-1.0-pro"
    ]
    model_choice = st.selectbox("Preferred Engine", model_options, index=0)
    
    st.divider()
    include_voice = st.toggle("AI Voiceovers", value=True)
    include_images = st.toggle("AI Imagery", value=True)

# ---------- INPUT AREA ----------
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    target_topic = st.text_input("", placeholder="Enter a topic (e.g. Gravity, The Deep Ocean, Mars Colony)...")
    generate_btn = st.button("🎬 RUN PRODUCTION")

# ---------- EXECUTION ----------
if generate_btn and target_topic:
    try:
        progress = st.status("🏗️ Building Concept...", expanded=False)
        
        # Step 1: Scripting
        progress.update(label="🖋️ Scripting Narrative...")
        story_data = generate_story(target_topic, style_choice, tone_choice, model_choice)
        st.session_state["active_story"] = story_data
        
        progress.update(label="✅ Script Finished!", state="complete")
        
        # Display Title
        st.markdown(f"## {story_data['title']}")
        st.markdown(f"<p style='text-align:center; font-style:italic;'>{story_data['hook']}</p>", unsafe_allow_html=True)
        st.divider()

        # Render Scenes
        for scene in story_data['scenes']:
            with st.container():
                st.markdown(f"""
                <div class="scene-container">
                    <div class="scene-meta">Scene {scene['id']} • Cinematic Director's Cut</div>
                    <h3>{scene['title']}</h3>
                    <p style='font-size: 1.1rem; line-height: 1.7;'>{scene['content']}</p>
                    <div class="narration-script">
                        <b>Narrator:</b> "{scene['voice']}"
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Media Row
                m1, m2 = st.columns([1, 1])
                with m1:
                    if include_images:
                        img_url = get_cinematic_image(f"{scene['visual']}, style: {style_choice}")
                        st.image(img_url, use_container_width=True)
                with m2:
                    if include_voice:
                        audio_file = generate_audio(scene['voice'], scene['id'])
                        st.audio(audio_file)
            st.divider()
            
        # Download Script
        st.download_button("📥 Download JSON Script", json.dumps(story_data, indent=2), "story_script.json")

    except Exception as e:
        st.error(f"🎬 Production Interrupted: {e}")

# ---------- FOOTER ----------
st.markdown("<br><p style='text-align:center; opacity:0.3; font-size: 0.8rem;'>StoryLens v2 • Built for AI Creators</p>", unsafe_allow_html=True)
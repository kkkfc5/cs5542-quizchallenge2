import os
import time
import logging
from datetime import datetime
import threading
import whisper
import numpy as np
import sounddevice as sd
import soundfile as sf
from flask import Flask, render_template, request, jsonify

from core_engine import generate_chapter_stream, generate_chapter_summary, process_and_play_stream

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# ==========================================
# GLOBAL STATE & CONFIG
# ==========================================
BASE_STORIES_DIR = "stories"
ACTIVE_STORY_DIR = ""
OLLAMA_MODEL = "llama3"

STORY_STATE = "IDLE" 
NEXT_PROMPT = "" 
RECORDING = False
AUDIO_BUFFER = []
CURRENT_AUDIO_STREAM = None 

PAST_STORY_TEXT = ""
CURRENT_CHAPTER_TEXT = ""

# NEW: A thread-safe flag to signal a halt
HALT_EVENT = threading.Event()

print("🎧 Loading Whisper Model...")
stt_model = whisper.load_model("base")

# ==========================================
# FILE MANAGEMENT & MEMORY
# ==========================================
def setup_directories():
    os.makedirs(BASE_STORIES_DIR, exist_ok=True)

def refresh_past_text():
    """Reads all saved chapters of the active story to display in the UI."""
    global PAST_STORY_TEXT
    PAST_STORY_TEXT = ""
    if not ACTIVE_STORY_DIR: return
    
    chapter_files = [f for f in os.listdir(ACTIVE_STORY_DIR) if f.startswith("chapter_")]
    chapter_files.sort()
    
    for file in chapter_files:
        with open(os.path.join(ACTIVE_STORY_DIR, file), "r", encoding="utf-8") as f:
            PAST_STORY_TEXT += f.read().strip() + "\n\n"

def create_new_story():
    global ACTIVE_STORY_DIR, PAST_STORY_TEXT, CURRENT_CHAPTER_TEXT
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ACTIVE_STORY_DIR = os.path.join(BASE_STORIES_DIR, f"Story_{timestamp}")
    os.makedirs(ACTIVE_STORY_DIR, exist_ok=True)
    with open(os.path.join(ACTIVE_STORY_DIR, "story_memory.txt"), "w", encoding="utf-8") as f:
        f.write("")
    PAST_STORY_TEXT = ""
    CURRENT_CHAPTER_TEXT = ""

def get_story_context():
    if not ACTIVE_STORY_DIR: return "", 1
    memory_path = os.path.join(ACTIVE_STORY_DIR, "story_memory.txt")
    with open(memory_path, "r", encoding="utf-8") as f:
        summaries = f.read().strip()
        
    chapter_files = [f for f in os.listdir(ACTIVE_STORY_DIR) if f.startswith("chapter_")]
    last_chapter_text = ""
    next_chapter_num = 1
    
    if chapter_files:
        chapter_files.sort()
        next_chapter_num = len(chapter_files) + 1
        with open(os.path.join(ACTIVE_STORY_DIR, chapter_files[-1]), "r", encoding="utf-8") as f:
            last_chapter_text = f.read().strip()
            
    context = f"PREVIOUS SUMMARIES:\n{summaries}\n\n"
    if last_chapter_text:
        context += f"IMMEDIATELY PRECEDING CHAPTER TEXT:\n{last_chapter_text}"
    return context, next_chapter_num

def save_chapter(chapter_num, full_text, summary_text):
    with open(os.path.join(ACTIVE_STORY_DIR, "story_memory.txt"), "a", encoding="utf-8") as f:
        f.write(f"Chapter {chapter_num}: {summary_text}\n")
    with open(os.path.join(ACTIVE_STORY_DIR, f"chapter_{chapter_num:02d}.txt"), "w", encoding="utf-8") as f:
        f.write(full_text.strip())

# ==========================================
# THE CONTINUOUS STORY LOOP
# ==========================================
def continuous_story_loop():
    global STORY_STATE, NEXT_PROMPT, CURRENT_CHAPTER_TEXT, PAST_STORY_TEXT
    
    print("\n🌐 Web server running at http://localhost:5000")

    while True:
        if STORY_STATE in ["IDLE", "WAITING_FOR_INPUT"]:
            time.sleep(0.5) 
            continue
            
        if STORY_STATE == "PAUSE_REQUESTED":
            STORY_STATE = "WAITING_FOR_INPUT"
            continue

        if STORY_STATE == "GENERATING":
            CURRENT_CHAPTER_TEXT = "" 
            HALT_EVENT.clear() 
            context, next_chapter_num = get_story_context()
            
            # EVALUATION METRIC 1: Start the stopwatch right before LLM is called
            start_time = time.time()
            
            story_stream = generate_chapter_stream(OLLAMA_MODEL, NEXT_PROMPT, context)
            full_generated_text = ""
            
            def capture_stream():
                nonlocal full_generated_text
                global CURRENT_CHAPTER_TEXT
                for line in story_stream:
                    full_generated_text += line + "\n"
                    CURRENT_CHAPTER_TEXT += line + "\n"
                    yield line
            
            try:
                # Pass the stopwatch start_time into the stream processor
                process_and_play_stream(
                    capture_stream(), 
                    lambda: HALT_EVENT.is_set(), 
                    generation_start_time=start_time
                )
                
                if HALT_EVENT.is_set():
                    print("\n🛑 HALT ACKNOWLEDGED. Discarding partial generation.")
                    CURRENT_CHAPTER_TEXT += "\n\n[ 🛑 Generation Halted by User. ]"
                    STORY_STATE = "WAITING_FOR_INPUT"
                    continue 
                
                summary = generate_chapter_summary(OLLAMA_MODEL, full_generated_text)
                save_chapter(next_chapter_num, full_generated_text, summary)
                PAST_STORY_TEXT += full_generated_text + "\n\n"
                CURRENT_CHAPTER_TEXT = ""
                
            except Exception as e:
                print(f"❌ Error: {e}")
                STORY_STATE = "IDLE"
                continue
            
            NEXT_PROMPT = "Continue the story naturally to the next exciting event."

# ==========================================
# FLASK WEB ROUTES (The API)
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    return jsonify({"state": STORY_STATE})

@app.route('/api/text')
def get_text():
    return jsonify({
        "past_text": PAST_STORY_TEXT,
        "current_text": CURRENT_CHAPTER_TEXT
    })

@app.route('/api/stories', methods=['GET'])
def list_stories():
    folders = [f for f in os.listdir(BASE_STORIES_DIR) if os.path.isdir(os.path.join(BASE_STORIES_DIR, f))]
    folders.sort(reverse=True) # Newest first
    return jsonify({"stories": folders, "active": os.path.basename(ACTIVE_STORY_DIR) if ACTIVE_STORY_DIR else None})

@app.route('/api/load_story', methods=['POST'])
def load_story():
    global STORY_STATE, ACTIVE_STORY_DIR
    if STORY_STATE == "GENERATING":
        return jsonify({"error": "Cannot change story while generating!"}), 400
        
    data = request.json
    folder_name = data.get('story_id')
    if folder_name:
        ACTIVE_STORY_DIR = os.path.join(BASE_STORIES_DIR, folder_name)
        refresh_past_text()
        STORY_STATE = "WAITING_FOR_INPUT"
        return jsonify({"status": f"Loaded {folder_name}"})
    return jsonify({"error": "Invalid story id"}), 400

@app.route('/api/start_new')
def start_new():
    global STORY_STATE
    create_new_story()
    STORY_STATE = "WAITING_FOR_INPUT"
    return jsonify({"status": "Started new story, waiting for prompt."})

@app.route('/api/pause')
def request_pause():
    global STORY_STATE
    if STORY_STATE == "GENERATING":
        STORY_STATE = "PAUSE_REQUESTED"
    return jsonify({"status": "Pause scheduled."})

@app.route('/api/continue')
def api_continue():
    global STORY_STATE, NEXT_PROMPT
    if STORY_STATE == "WAITING_FOR_INPUT":
        NEXT_PROMPT = "Continue the story naturally to the next exciting event."
        STORY_STATE = "GENERATING"
        return jsonify({"status": "Continuing naturally."})
    return jsonify({"error": "Can only continue when paused."}), 400

@app.route('/api/halt')
def request_halt():
    global STORY_STATE
    if STORY_STATE == "GENERATING":
        # 1. Flip the event flag for the Python loops
        HALT_EVENT.set()
        # 2. Instantly kill any hardware audio currently playing
        sd.stop() 
        return jsonify({"status": "Halt triggered."})
    return jsonify({"status": "Nothing to halt."})

@app.route('/api/record/start', methods=['POST'])
def start_record():
    global RECORDING, AUDIO_BUFFER, CURRENT_AUDIO_STREAM
    RECORDING = True
    AUDIO_BUFFER = []
    def callback(indata, frames, time, status):
        if RECORDING: AUDIO_BUFFER.append(indata.copy())

    CURRENT_AUDIO_STREAM = sd.InputStream(samplerate=16000, channels=1, callback=callback)
    CURRENT_AUDIO_STREAM.start()
    return jsonify({"status": "Recording started"})

@app.route('/api/record/stop', methods=['POST'])
def stop_record():
    global RECORDING, AUDIO_BUFFER, NEXT_PROMPT, STORY_STATE, CURRENT_AUDIO_STREAM
    RECORDING = False
    if CURRENT_AUDIO_STREAM:
        CURRENT_AUDIO_STREAM.stop()
        CURRENT_AUDIO_STREAM.close()
    
    if AUDIO_BUFFER:
        audio_data = np.concatenate(AUDIO_BUFFER, axis=0)
        sf.write("temp_input.wav", audio_data, 16000)
        result = stt_model.transcribe("temp_input.wav")
        NEXT_PROMPT = result["text"].strip()
        STORY_STATE = "GENERATING" 
        return jsonify({"transcription": NEXT_PROMPT})
    return jsonify({"error": "No audio captured"})

if __name__ == "__main__":
    setup_directories()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True).start()
    try:
        continuous_story_loop()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
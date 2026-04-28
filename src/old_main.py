# import os
# import time
# import whisper
# import keyboard
# import numpy as np
# import sounddevice as sd
# import soundfile as sf
# import re

# # Import the functions we built in the previous step
# from core_engine import generate_chapter_stream, process_and_play_stream

# # ==========================================
# # MODULE 1: THE EARS (Input & Transcription)
# # ==========================================

# print("🎧 Loading Whisper Model (this takes a moment)...")
# stt_model = whisper.load_model("base") # 'base' is fast and uses ~1GB VRAM

# def record_and_transcribe():
#     """Waits for spacebar, records audio, waits for spacebar, transcribes."""
#     print("\n👉 PRESS SPACEBAR to start talking...")
#     keyboard.wait('space')
#     time.sleep(0.2) # Debounce to prevent double-press
    
#     print("🎙️ RECORDING... (Press spacebar again to stop)")
    
#     fs = 16000 # Whisper expects 16kHz
#     recording = []
    
#     # Callback to continuously capture audio chunks
#     def callback(indata, frames, time, status):
#         recording.append(indata.copy())

#     with sd.InputStream(samplerate=fs, channels=1, callback=callback):
#         keyboard.wait('space')
        
#     time.sleep(0.2) # Debounce
#     print("⏳ Processing speech...")
    
#     try:
#         # Combine chunks and save to temporary file
#         audio_data = np.concatenate(recording, axis=0)
#         temp_file = "temp_input.wav"
#         sf.write(temp_file, audio_data, fs)
        
#         # Transcribe with Whisper
#         result = stt_model.transcribe(temp_file)
#         child_prompt = result["text"].strip()
        
#         print(f"🧒 Child said: '{child_prompt}'")
#         return child_prompt
#     except Exception as e:
#         print(e)
#         return None

# # ==========================================
# # MODULE 2: THE BRAIN (Memory & Files)
# # ==========================================

# STORY_DIR = "active_story"

# def init_story_environment():
#     """Ensures the directory and memory file exist."""
#     os.makedirs(STORY_DIR, exist_ok=True)
#     memory_path = os.path.join(STORY_DIR, "story_memory.txt")
#     if not os.path.exists(memory_path):
#         with open(memory_path, "w", encoding="utf-8") as f:
#             f.write("") # Create empty file

# def get_story_context():
#     """Retrieves previous summaries and the full text of the LAST chapter."""
#     memory_path = os.path.join(STORY_DIR, "story_memory.txt")
    
#     # 1. Get Summaries
#     with open(memory_path, "r", encoding="utf-8") as f:
#         summaries = f.read().strip()
        
#     # 2. Find the last chapter file
#     files = os.listdir(STORY_DIR)
#     chapter_files = [f for f in files if f.startswith("chapter_") and f.endswith(".txt")]
    
#     last_chapter_text = ""
#     next_chapter_num = 1
    
#     if chapter_files:
#         chapter_files.sort() # Ensure chronological order
#         last_file = chapter_files[-1]
#         next_chapter_num = len(chapter_files) + 1
        
#         with open(os.path.join(STORY_DIR, last_file), "r", encoding="utf-8") as f:
#             last_chapter_text = f.read().strip()
            
#     # Combine context
#     context = f"PREVIOUS SUMMARIES:\n{summaries}\n\n"
#     if last_chapter_text:
#         context += f"IMMEDIATELY PRECEDING CHAPTER TEXT:\n{last_chapter_text}"
        
#     return context, next_chapter_num

# def save_chapter(chapter_num, full_text):
#     """Saves the chapter text and extracts/saves the summary."""
#     # Find the summary line using regex
#     summary_match = re.search(r'\[Summary\]:\s*(.*)', full_text, re.IGNORECASE)
#     summary_text = summary_match.group(1) if summary_match else "A chapter happened."
    
#     # Save the summary to memory
#     with open(os.path.join(STORY_DIR, "story_memory.txt"), "a", encoding="utf-8") as f:
#         f.write(f"Chapter {chapter_num}: {summary_text}\n")
        
#     # Save the raw chapter text
#     # Remove the summary line from the chapter text before saving so it doesn't get read next time
#     clean_text = re.sub(r'\[Summary\]:.*\n?', '', full_text, flags=re.IGNORECASE).strip()
    
#     with open(os.path.join(STORY_DIR, f"chapter_{chapter_num:02d}.txt"), "w", encoding="utf-8") as f:
#         f.write(clean_text)

# # ==========================================
# # MODULE 5: THE MAIN CONTROLLER
# # ==========================================

# def main():
#     print("\n" + "="*40)
#     print(" 📖 INFINITE BEDTIME STORYTELLER POC ")
#     print("="*40)
    
#     init_story_environment()
#     OLLAMA_MODEL = "llama3" # Ensure this matches your downloaded model
    
#     while True:
#         # 1. Listen and Transcribe
#         user_prompt = record_and_transcribe()
        
#         if not user_prompt:
#             print("Did not catch any audio. Try again.")
#             continue
            
#         # 2. Gather Context
#         context, next_chapter_num = get_story_context()
        
#         # 3. Stream Generation & Playback
#         # We need to capture the full text to save it later, so we will wrap the generator
#         story_stream = generate_chapter_stream(
#             model_name=OLLAMA_MODEL,
#             child_prompt=user_prompt,
#             previous_summaries=context
#         )
        
#         full_generated_text = ""
        
#         # Generator wrapper to capture the output while still yielding it to the TTS
#         def capture_stream():
#             nonlocal full_generated_text
#             for line in story_stream:
#                 full_generated_text += line + "\n"
#                 yield line
                
#         # Pass the wrapped stream to your existing audio player
#         process_and_play_stream(capture_stream())
        
#         # 4. Save to Disk
#         print("\n💾 Saving chapter...")
#         save_chapter(next_chapter_num, full_generated_text)
#         print(f"✅ Chapter {next_chapter_num} saved successfully!\n")

# if __name__ == "__main__":
#     # Note: Requires running as Administrator/Root for the keyboard library to work
#     main()

import os
import time
from datetime import datetime
import whisper
import keyboard
import numpy as np
import sounddevice as sd
import soundfile as sf

# Import from core_engine
from gitrepo.src.core_engine import generate_chapter_stream, generate_chapter_summary, process_and_play_stream

# Global configuration
BASE_STORIES_DIR = "stories"
ACTIVE_STORY_DIR = ""
OLLAMA_MODEL = "llama3"

print("🎧 Loading Whisper Model...")
stt_model = whisper.load_model("base")

# ==========================================
# FILE MANAGEMENT
# ==========================================

def setup_directories():
    os.makedirs(BASE_STORIES_DIR, exist_ok=True)

def create_new_story():
    global ACTIVE_STORY_DIR
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"Story_{timestamp}"
    ACTIVE_STORY_DIR = os.path.join(BASE_STORIES_DIR, folder_name)
    os.makedirs(ACTIVE_STORY_DIR, exist_ok=True)
    
    # Create empty memory file
    with open(os.path.join(ACTIVE_STORY_DIR, "story_memory.txt"), "w", encoding="utf-8") as f:
        f.write("")
    print(f"\n📂 Created new story folder: {folder_name}")

def load_existing_story():
    global ACTIVE_STORY_DIR
    folders = [f for f in os.listdir(BASE_STORIES_DIR) if os.path.isdir(os.path.join(BASE_STORIES_DIR, f))]
    
    if not folders:
        print("\n❌ No saved stories found. Starting a new one instead.")
        create_new_story()
        return True

    print("\n📂 Saved Stories:")
    for i, folder in enumerate(folders):
        print(f"[{i + 1}] {folder}")
        
    choice = input("\nEnter the number of the story to continue (or 0 to cancel): ")
    try:
        choice_idx = int(choice) - 1
        if choice_idx == -1: return False
        if 0 <= choice_idx < len(folders):
            ACTIVE_STORY_DIR = os.path.join(BASE_STORIES_DIR, folders[choice_idx])
            print(f"\n✅ Loaded: {folders[choice_idx]}")
            return True
        else:
            print("Invalid selection.")
            return False
    except ValueError:
        print("Invalid input.")
        return False

def get_story_context():
    memory_path = os.path.join(ACTIVE_STORY_DIR, "story_memory.txt")
    with open(memory_path, "r", encoding="utf-8") as f:
        summaries = f.read().strip()
        
    chapter_files = [f for f in os.listdir(ACTIVE_STORY_DIR) if f.startswith("chapter_")]
    last_chapter_text = ""
    next_chapter_num = 1
    
    if chapter_files:
        chapter_files.sort()
        last_file = chapter_files[-1]
        next_chapter_num = len(chapter_files) + 1
        with open(os.path.join(ACTIVE_STORY_DIR, last_file), "r", encoding="utf-8") as f:
            last_chapter_text = f.read().strip()
            
    context = f"PREVIOUS SUMMARIES:\n{summaries}\n\n"
    if last_chapter_text:
        context += f"IMMEDIATELY PRECEDING CHAPTER TEXT:\n{last_chapter_text}"
        
    return context, next_chapter_num

def save_chapter(chapter_num, full_text, summary_text):
    # Save memory
    with open(os.path.join(ACTIVE_STORY_DIR, "story_memory.txt"), "a", encoding="utf-8") as f:
        f.write(f"Chapter {chapter_num}: {summary_text}\n")
    # Save text
    with open(os.path.join(ACTIVE_STORY_DIR, f"chapter_{chapter_num:02d}.txt"), "w", encoding="utf-8") as f:
        f.write(full_text.strip())

# ==========================================
# AUDIO INPUT
# ==========================================

def record_and_transcribe():
    print("\n👉 PRESS SPACEBAR to start talking...")
    keyboard.wait('space')
    time.sleep(0.2)
    print("🎙️ RECORDING... (Press spacebar again to stop)")
    
    fs = 16000
    recording = []
    def callback(indata, frames, time, status):
        recording.append(indata.copy())

    with sd.InputStream(samplerate=fs, channels=1, callback=callback):
        keyboard.wait('space')
        
    time.sleep(0.2)
    print("⏳ Processing speech...")
    audio_data = np.concatenate(recording, axis=0)
    sf.write("temp_input.wav", audio_data, fs)
    
    result = stt_model.transcribe("temp_input.wav")
    return result["text"].strip()

# ==========================================
# MAIN LOOP
# ==========================================

def play_chapter_loop():
    while True:
        user_prompt = record_and_transcribe()
        if not user_prompt: continue
            
        context, next_chapter_num = get_story_context()
        
        story_stream = generate_chapter_stream(OLLAMA_MODEL, user_prompt, context)
        full_generated_text = ""
        
        def capture_stream():
            nonlocal full_generated_text
            for line in story_stream:
                full_generated_text += line + "\n"
                yield line
                
        # Play the audio in real-time
        process_and_play_stream(capture_stream())
        
        # Once audio is done playing, generate the summary
        summary = generate_chapter_summary(OLLAMA_MODEL, full_generated_text)
        print(f"\n📝 Extracted Summary: {summary}")
        
        save_chapter(next_chapter_num, full_generated_text, summary)
        print(f"💾 Chapter {next_chapter_num} saved to {ACTIVE_STORY_DIR}\n")
        
        print("-" * 30)
        print("Ready for the next chapter! (Or press Ctrl+C to exit to menu)")

def main():
    setup_directories()
    
    while True:
        print("\n" + "="*40)
        print(" 📖 INFINITE BEDTIME STORYTELLER")
        print("="*40)
        print("[1] Start a New Story")
        print("[2] Continue an Existing Story")
        print("[3] Exit")
        print("="*40)
        
        choice = input("Select an option (1-3): ")
        
        if choice == "1":
            create_new_story()
            try:
                play_chapter_loop()
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                
        elif choice == "2":
            if load_existing_story():
                try:
                    play_chapter_loop()
                except KeyboardInterrupt:
                    print("\nReturning to main menu...")
                    
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
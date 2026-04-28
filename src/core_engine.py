# import ollama
# import re
# import sounddevice as sd
# from kokoro import KPipeline

# # ==========================================
# # MODULE 3: THE STORYTELLER (OLLAMA)
# # ==========================================

# def generate_chapter_stream(model_name, child_prompt, previous_summaries=""):
#     """
#     Streams output from Ollama, yielding one complete sentence/line at a time.
#     """
#     system_instruction = """You are a friendly, creative children's bedtime storyteller.
#     You MUST output your story line by line.
#     You MUST start every single line with a speaker tag in brackets, followed by a colon.
    
#     Rules:
#     1. The very first line MUST be a short summary of what is about to happen, tagged as [Summary]:
#     2. The narrator's lines MUST be tagged as [Narrator]:
#     3. Character lines MUST be tagged with their name, e.g., [Timmy]: or [Dragon]:
    
#     Keep the story engaging, safe, and relatively short for this chapter."""

#     full_prompt = f"Previous Story Context: {previous_summaries}\n\nChild's Request: {child_prompt}"

#     print("🧠 [LLM] Thinking...")
    
#     response = ollama.chat(
#         model=model_name,
#         messages=[
#             {'role': 'system', 'content': system_instruction},
#             {'role': 'user', 'content': full_prompt}
#         ],
#         stream=True
#     )

#     buffer = ""
#     for chunk in response:
#         content = chunk['message']['content']
#         buffer += content
        
#         # When a newline is detected, yield the completed line
#         if '\n' in buffer:
#             lines = buffer.split('\n')
#             # Yield all complete lines except the last incomplete chunk
#             for line in lines[:-1]:
#                 if line.strip():
#                     yield line.strip()
#             # Keep the incomplete chunk in the buffer
#             buffer = lines[-1]
            
#     # Yield any remaining text in the buffer after the stream ends
#     if buffer.strip():
#         yield buffer.strip()

# # ==========================================
# # MODULE 4: THE VOICE (KOKORO TTS)
# # ==========================================

# # Initialize Kokoro Pipeline (English)
# # This will download the model (~80MB) on the first run.
# print("🎙️ [TTS] Initializing Kokoro...")
# pipeline = KPipeline(lang_code='a') 

# # Map character tags to specific Kokoro voice IDs.
# # You can browse available Kokoro voices in their documentation.
# VOICE_MAP = {
#     "narrator": "af_bella",   # American Female - smooth and clear
#     "dragon": "am_onyx",      # American Male - deep and strong
#     "timmy": "am_puck",       # American Male - higher pitched/youthful
#     "default": "af_heart"     # Fallback voice
# }

# def play_audio(audio_data, sample_rate=24000):
#     """Plays the numpy audio array through system speakers."""
#     sd.play(audio_data, sample_rate)
#     sd.wait() # Wait until the audio finishes playing before continuing

# def process_and_play_stream(text_generator):
#     """
#     Consumes the LLM text generator line-by-line, assigns voices, and plays audio.
#     """
#     for line in text_generator:
#         # Regex to extract the speaker tag and the dialogue text
#         # Matches "[Speaker]: Text"
#         match = re.match(r'\[(.*?)\]:\s*(.*)', line)
        
#         if match:
#             speaker = match.group(1).strip().lower()
#             text = match.group(2).strip()
#         else:
#             # Fallback if the LLM forgets the tag format
#             speaker = "narrator"
#             text = line

#         # 1. Handle the Summary Tag
#         if speaker == "summary":
#             print(f"\n📝 [SAVING TO MEMORY]: {text}\n")
#             # In Module 2, you will write this string to story_memory.txt
#             continue

#         # 2. Handle Dialogue
#         # Get the specific voice, or use the default if the character is new/unmapped
#         voice_id = VOICE_MAP.get(speaker, VOICE_MAP["default"])
        
#         print(f"🗣️ [{speaker.capitalize()}] ({voice_id}): {text}")

#         # Generate audio using Kokoro
#         # Pipeline returns a generator of (graphemes, phonemes, audio)
#         audio_generator = pipeline(
#             text, 
#             voice=voice_id, 
#             speed=1.0, 
#             split_pattern=r'\n+'
#         )

#         for _, _, audio in audio_generator:
#             play_audio(audio, 24000)

# # ==========================================
# # TEST EXECUTION
# # ==========================================

# if __name__ == "__main__":
#     # Setup test parameters
#     OLLAMA_MODEL = "llama3" # Change to 'phi3' or whatever model you pulled
#     TEST_PROMPT = "A little boy named Timmy meets a friendly dragon who loves pancakes."
    
#     print("\n--- Starting Storyteller POC ---")
#     print(f"Prompt: {TEST_PROMPT}\n")
    
#     # 1. Create the text stream (Module 3)
#     story_stream = generate_chapter_stream(
#         model_name=OLLAMA_MODEL, 
#         child_prompt=TEST_PROMPT
#     )
    
#     # 2. Pass the stream directly into the audio player (Module 4)
#     process_and_play_stream(story_stream)
    
#     print("\n--- Chapter Complete ---")


import ollama
import re
import time
import sounddevice as sd
from kokoro import KPipeline

# Initialize Kokoro Pipeline
print("🎙️ [TTS] Initializing Kokoro...")
pipeline = KPipeline(lang_code='a') 

VOICE_MAP = {
    "narrator": "af_bella",
    "dragon": "am_onyx",
    "timmy": "am_puck",
    "default": "af_heart"
}

def generate_chapter_stream(model_name, child_prompt, previous_summaries=""):
    # """BASELINE EVALUATION VERSION (Non-Streaming)"""
    
    # # ... (Keep your modified baseline system_instruction here) ...
    # system_instruction = "You are a storyteller. Write a story with characters talking." 
    
    # full_prompt = f"Previous Story Context: {previous_summaries}\n\nChild's Request: {child_prompt}"

    # print("🧠 [LLM] Generating entire story at once (Baseline Mode)...")
    
    # # stream=False returns the entire completed dictionary
    # response = ollama.chat(
    #     model=model_name,
    #     messages=[
    #         {'role': 'system', 'content': system_instruction},
    #         {'role': 'user', 'content': full_prompt}
    #     ],
    #     stream=False 
    # )

    # # 1. Grab the massive, completed block of text
    # full_text = response['message']['content']
    
    # # 2. Yield it line-by-line so the Kokoro TTS parser still works
    # for line in full_text.split('\n'):
    #     if line.strip():
    #         yield line.strip()
    # return
    
    
    """Streams output from Ollama line-by-line."""
    # Notice: We removed the summary instruction from the system prompt
    system_instruction = """You are a friendly, creative children's bedtime storyteller.
    You MUST output your story line by line.
    You MUST start every single line with a speaker tag in brackets, followed by a colon.
    
    Rules:
    1. The narrator's lines MUST be tagged as [Narrator]:
    2. Character lines MUST be tagged with their name, e.g., [Timmy]: or [Dragon]:
    
    Keep the story engaging, safe, and relatively short for this chapter.
    
    Do not speak as yourself.
    Do not ask what will happen next after generating."""


    # #TODO : DELETE THIS ####################################################################
    # #TODO : DELETE THIS ####################################################################
    # #TODO : DELETE THIS ####################################################################
    # #TODO : DELETE THIS ####################################################################
    # #TODO : DELETE THIS ####################################################################
    # system_instruction = '''You are a children's storyteller. Write a short story with characters talking.'''


    full_prompt = f"Previous Story Context: {previous_summaries}\n\nChild's Request: {child_prompt}"

    print("🧠 [LLM] Generating story...")
    
    response = ollama.chat(
        model=model_name,
        messages=[
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': full_prompt}
        ],
        stream=True
        # stream=False
    )

    buffer = ""
    for chunk in response:
        content = chunk['message']['content']
        buffer += content
        if '\n' in buffer:
            lines = buffer.split('\n')
            for line in lines[:-1]:
                if line.strip():
                    yield line.strip()
            buffer = lines[-1]
            
    if buffer.strip():
        yield buffer.strip()

def generate_chapter_summary(model_name, full_chapter_text):
    """A secondary, fast LLM call to summarize the completed chapter."""
    print("\n🧠 [LLM] Generating chapter summary for memory...")
    prompt = f"Summarize the following story chapter in exactly one short sentence:\n\n{full_chapter_text}"
    
    response = ollama.chat(
        model=model_name,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response['message']['content'].strip()

def play_audio(audio_data, sample_rate=24000):
    sd.play(audio_data, sample_rate)
    sd.wait()

def process_and_play_stream(text_generator, check_halt_callback=None, generation_start_time=None):
    """
    Consumes the stream, plays audio, and tracks Evaluation Metrics.
    """
    first_audio_played = False
    total_lines = 0
    format_errors = 0

    for line in text_generator:
        if check_halt_callback and check_halt_callback(): break
        
        # Skip empty lines for metric counting
        if not line.strip(): continue

        total_lines += 1
        
        # METRIC 2 CHECK: Does it match the [Speaker]: format?
        match = re.match(r'\[(.*?)\]:\s*(.*)', line)
        # print(f"\n: RAW : {line}")
        if match:
            speaker = match.group(1).strip().lower()
            text = match.group(2).strip()
        else:
            # The LLM hallucinated the format
            speaker = "narrator"
            text = line
            format_errors += 1
            print(f"\n: BROKEN LINE : {line}") 


        voice_id = VOICE_MAP.get(speaker, VOICE_MAP["default"])
        print(f"🗣️ [{speaker.capitalize()}] ({voice_id}): {text}")

        audio_generator = pipeline(text, voice=voice_id, speed=1.0, split_pattern=r'\n+')
        
        for _, _, audio in audio_generator:
            if check_halt_callback and check_halt_callback(): break

            # METRIC 1 CHECK: Time to first audio
            if not first_audio_played and generation_start_time:
                latency = time.time() - generation_start_time
                print(f"\n⏱️ [EVALUATION] Time-to-First-Audio Latency: {latency:.2f} seconds\n")
                first_audio_played = True

            play_audio(audio, 24000)

    # Output Metric 2 at the end of the chapter
    if total_lines > 0:
        adherence = ((total_lines - format_errors) / total_lines) * 100
        print(f"\n📊 [EVALUATION] Format Adherence: {adherence:.1f}% ({total_lines - format_errors}/{total_lines} lines correctly tagged)\n")

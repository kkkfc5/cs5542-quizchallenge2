# To Run:

## Prerequisites: 
1. FFMPEG
Windows Admin Terminal:
```winget install ffmpeg```

2. Ollama running Llama3

## Setup:
1. Run:
```python src/app.py```

2. Navigate to:
```http://localhost:5000```



# Data Flow / Architecture Graph:

flowchart TD
    subgraph UI_Layer [1. Interaction Layer]
        Mic[Microphone] -->|Raw Audio Buffer| Whisper[Whisper STT]
        Whisper -->|Transcribed Text| State[State: NEXT_PROMPT]
        WebBtn[UI: Continue Button] -->|Default Text| State
        WebHalt[UI: Halt Button] -->|Set Event Flag| HaltSignal((Halt Event))
    end

    subgraph Memory_Layer [2. Context Assembly]
        MemFile[(story_memory.txt)] -->|Past Summaries| Builder{Prompt Constructor}
        ChapFile[(Previous chapter.txt)] -->|Last Chapter Text| Builder
        State --> Builder
        SysPrompt[System Rules & Tags] --> Builder
    end

    subgraph LLM_Layer [3. The Brain]
        Builder -->|Full Context Payload| Ollama[Llama 3 Local API]
    end

    subgraph Output_Layer [4. Streaming Execution]
        Ollama -->|Yields Line-by-Line| Parser{Text Parser & Router}
        Parser -->|Check Flag| HaltSignal
        Parser -->|Raw Text| TextBuffer[UI: Text Display]
        Parser -->|Extract [Speaker] Tag| VoiceSelector[Voice Profile Matcher]
        VoiceSelector -->|Text + Voice ID| Kokoro[Kokoro TTS Engine]
        Kokoro -->|Audio Array| Speaker[System Speakers]
    end

    subgraph Post_Processing [5. Memory Management]
        Ollama -.->|Chapter Complete| Summarizer[Secondary LLM Call]
        Summarizer -->|1-Sentence Recap| MemFile
        Ollama -.->|Full Text| NewChap[(New chapter.txt)]
    end

    UI_Layer --> Memory_Layer
    Memory_Layer --> LLM_Layer
    LLM_Layer --> Output_Layer
    Output_Layer -.->|Triggers upon completion| Post_Processing

    classDef hardware fill:#45475a,stroke:#cba6f7,stroke-width:2px,color:#fff;
    classDef memory fill:#313244,stroke:#a6e3a1,stroke-width:2px,color:#fff;
    classDef logic fill:#1e1e2e,stroke:#89b4fa,stroke-width:2px,color:#fff;
    
    class Mic,Speaker hardware;
    class MemFile,ChapFile,NewChap memory;
    class Builder,Parser,VoiceSelector logic;
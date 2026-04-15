# --- FILE: file_processor.py ---
"""
file_processor.py — Panda AI V5 Multimodal File Processor
Supports: PDF, DOCX, XLSX, PPTX, JPG/PNG (OCR), MP3/WAV, MP4
Uses semantic chunking to stay within Groq token limits.
"""

import os
import re
import tempfile

UPLOAD_DIR = "uploads"
os.makedirs(f"{UPLOAD_DIR}/documents", exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/images",    exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/audio",     exist_ok=True)

ALLOWED_EXTENSIONS = {
    'pdf', 'docx', 'xlsx', 'xls', 'pptx',
    'jpg', 'jpeg', 'png', 'bmp', 'tiff',
    'mp3', 'wav', 'ogg', 'mp4', 'avi', 'mov'
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

# ── Clean extracted text ──
def clean_extracted_text(text, limit=8000):
    if not text:
        return ""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    text = text.strip()
    return text[:limit]

# ── Semantic Chunking ──
def chunk_text(text, chunk_size=1500):
    """Split text into chunks of ~chunk_size words."""
    words  = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def find_relevant_chunks(chunks, question, top_n=2):
    """Find most relevant chunks based on keyword overlap."""
    if not chunks:
        return ""
    q_words = set(re.sub(r'[^\w\s]', '', question.lower()).split())
    scores  = []
    for chunk in chunks:
        c_words = set(chunk.lower().split())
        score   = len(q_words & c_words)
        scores.append(score)
    # Get top_n chunks
    sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    top_chunks = [chunks[i] for i in sorted_idx[:top_n]]
    return "\n\n---\n\n".join(top_chunks)

# ════════════════════════════════════════
# PDF Extraction
# ════════════════════════════════════════
def extract_pdf(file_path):
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        full_text = "\n\n".join(text_parts)
        print(f"PDF extracted: {len(full_text)} chars, {len(pdf.pages)} pages")
        return clean_extracted_text(full_text)
    except ImportError:
        return "[PDF extraction unavailable: pdfplumber not installed]"
    except Exception as e:
        print(f"PDF error: {e}")
        return f"[PDF extraction failed: {e}]"

# ════════════════════════════════════════
# Word (.docx) Extraction
# ════════════════════════════════════════
def extract_word(file_path):
    try:
        from docx import Document
        doc   = Document(file_path)
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        full  = "\n".join(paras)
        print(f"DOCX extracted: {len(full)} chars")
        return clean_extracted_text(full)
    except ImportError:
        return "[Word extraction unavailable: python-docx not installed]"
    except Exception as e:
        print(f"DOCX error: {e}")
        return f"[Word extraction failed: {e}]"

# ════════════════════════════════════════
# Excel (.xlsx) Extraction
# ════════════════════════════════════════
def extract_excel(file_path):
    try:
        import openpyxl
        wb    = openpyxl.load_workbook(file_path, data_only=True)
        parts = []
        for sheet in wb.worksheets:
            parts.append(f"Sheet: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join(str(c) for c in row if c is not None)
                if row_text.strip():
                    parts.append(row_text)
        full = "\n".join(parts)
        print(f"Excel extracted: {len(full)} chars")
        return clean_extracted_text(full)
    except ImportError:
        return "[Excel extraction unavailable: openpyxl not installed]"
    except Exception as e:
        print(f"Excel error: {e}")
        return f"[Excel extraction failed: {e}]"

# ════════════════════════════════════════
# PowerPoint (.pptx) Extraction
# ════════════════════════════════════════
def extract_pptx(file_path):
    try:
        from pptx import Presentation
        prs   = Presentation(file_path)
        parts = []
        for i, slide in enumerate(prs.slides, 1):
            parts.append(f"[Slide {i}]")
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    parts.append(shape.text.strip())
        full = "\n".join(parts)
        print(f"PPTX extracted: {len(full)} chars")
        return clean_extracted_text(full)
    except ImportError:
        return "[PPT extraction unavailable: python-pptx not installed]"
    except Exception as e:
        print(f"PPTX error: {e}")
        return f"[PPT extraction failed: {e}]"

# ════════════════════════════════════════
# Image OCR Extraction
# ════════════════════════════════════════
def extract_image(file_path):
    try:
        import pytesseract
        from PIL import Image
        img  = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        text = text.strip()
        print(f"OCR extracted: {len(text)} chars")
        return clean_extracted_text(text) if text else "[No text found in image]"
    except ImportError:
        return "[Image OCR unavailable: pytesseract not installed]"
    except Exception as e:
        print(f"Image OCR error: {e}")
        return f"[Image extraction failed: {e}]"

# ════════════════════════════════════════
# Audio Transcription
# ════════════════════════════════════════
def extract_audio(file_path):
    try:
        import whisper
        print(f"Transcribing audio: {file_path}")
        model  = whisper.load_model("tiny")  # fastest free model
        result = model.transcribe(file_path)
        text   = result.get("text", "").strip()
        print(f"Audio transcribed: {len(text)} chars")
        return clean_extracted_text(text) if text else "[No speech detected in audio]"
    except ImportError:
        # Fallback: SpeechRecognition
        try:
            import speech_recognition as sr
            r    = sr.Recognizer()
            with sr.AudioFile(file_path) as source:
                audio = r.record(source)
            text = r.recognize_google(audio)
            return clean_extracted_text(text)
        except Exception:
            return "[Audio transcription unavailable]"
    except Exception as e:
        print(f"Audio error: {e}")
        return f"[Audio extraction failed: {e}]"

# ════════════════════════════════════════
# Video Processing (extract audio → transcribe)
# ════════════════════════════════════════
def extract_video(file_path):
    try:
        from moviepy.editor import VideoFileClip
        audio_path = os.path.join(UPLOAD_DIR, "audio", "temp_audio.wav")
        print(f"Extracting audio from video: {file_path}")
        clip = VideoFileClip(file_path)
        clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
        clip.close()
        # Transcribe extracted audio
        return extract_audio(audio_path)
    except ImportError:
        return "[Video processing unavailable: moviepy not installed]"
    except Exception as e:
        print(f"Video error: {e}")
        return f"[Video extraction failed: {e}]"

# ════════════════════════════════════════
# MAIN: process_file()
# Called from app.py
# ════════════════════════════════════════
def process_file(file_path, filename):
    """
    Main entry point — detects file type and extracts text.
    Returns: (extracted_text, file_type)
    """
    ext = get_extension(filename)

    if ext == 'pdf':
        return extract_pdf(file_path),   'PDF'
    elif ext == 'docx':
        return extract_word(file_path),  'Word'
    elif ext in ('xlsx', 'xls'):
        return extract_excel(file_path), 'Excel'
    elif ext == 'pptx':
        return extract_pptx(file_path),  'PowerPoint'
    elif ext in ('jpg', 'jpeg', 'png', 'bmp', 'tiff'):
        return extract_image(file_path), 'Image'
    elif ext in ('mp3', 'wav', 'ogg'):
        return extract_audio(file_path), 'Audio'
    elif ext in ('mp4', 'avi', 'mov'):
        return extract_video(file_path), 'Video'
    else:
        return "[Unsupported file type]", 'Unknown'

# ════════════════════════════════════════
# Mixed Input: multiple files + question
# ════════════════════════════════════════
def process_mixed_files(file_paths_names, question):
    """
    Handle multiple files uploaded together.
    Returns combined relevant context for Groq.
    """
    all_sections = []

    for file_path, filename in file_paths_names:
        text, ftype = process_file(file_path, filename)
        if text and not text.startswith('['):
            all_sections.append(f"=== {ftype} File: {filename} ===\n{text}")

    if not all_sections:
        return ""

    combined = "\n\n".join(all_sections)
    chunks   = chunk_text(combined, chunk_size=1500)
    relevant = find_relevant_chunks(chunks, question, top_n=2)

    print(f"Mixed input: {len(all_sections)} files, {len(chunks)} chunks, relevant: {len(relevant)} chars")
    return relevant
import os
import io
import base64
from datetime import datetime
import re
from flask import Flask, flash, render_template, request, redirect, send_file, send_from_directory, session
from PyPDF2 import PdfReader
from gtts import gTTS
import google.generativeai as geai

app = Flask(__name__)
app.secret_key = 'SpeechProject'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Gemini setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Configure Generative AI API Key
geai.configure(api_key=GEMINI_API_KEY)

# --- Helpers ---
def extract_pdf_text(file_path):
    reader = PdfReader(file_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def clean_text(text):
    return re.sub(r'[*_`]+', '', text).strip()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_tts(text, output_path):
    tts = gTTS(text=text)
    tts.save(output_path)


# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/book', methods=['POST'])
def handle_book_question():
    pdf_file = request.files.get("pdf_file")
    audio_data = request.form.get("audio_data")

    if not pdf_file or not audio_data:
        flash("Both PDF and audio question are required.")
        return redirect('/')

    # Save PDF and audio
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    pdf_filename = f"book-{timestamp}.pdf"
    audio_filename = f"question-{timestamp}.wav"
    response_filename = f"response-{timestamp}.txt"
    tts_filename = f"tts-{timestamp}.wav"

    pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
    audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
    response_path = os.path.join(UPLOAD_FOLDER, response_filename)
    tts_path = os.path.join(UPLOAD_FOLDER, tts_filename)

    pdf_file.save(pdf_path)
    with open(audio_path, "wb") as f:
        f.write(base64.b64decode(audio_data))

    # Extract book text
    book_text = extract_pdf_text(pdf_path)[:5000]  # Truncate if needed
    encoded_audio = base64.b64encode(open(audio_path, "rb").read()).decode("utf-8")

    # Gemini prompt
    prompt = f"""
You are a helpful assistant with access to the following book:

{book_text}

1. Transcribe the user’s audio question.
2. Answer the question based only on the content of the book.
3. If you cannot find the answer in the book, say "This information is not in the book."

Please format as:
Transcription: ...
Answer: ...
"""

    model = geai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content([
        prompt,
        {"mime_type": "audio/wav", "data": encoded_audio}
    ])

    response_text = response.text.strip()
    transcript, answer = "N/A", "Could not generate response."

    if "Answer:" in response_text:
        parts = response_text.split("Answer:")
        transcript = clean_text(parts[0].replace("Transcription:", "").strip())
        answer = clean_text(parts[1])
    else:
        answer = response_text.strip()

    # Save response and generate TTS
    with open(response_path, "w") as f:
        f.write(f"Transcription: {transcript}\nAnswer: {answer}")

    generate_tts(answer, tts_path)

    # Store in session
    session["transcript"] = transcript
    session["answer"] = answer
    session["tts_audio"] = tts_filename

    return redirect('/')

@app.route('/tts/<filename>')
def serve_tts(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True)

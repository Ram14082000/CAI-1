from datetime import datetime
import io
import os
import base64
from flask import Flask, flash, render_template, request, redirect, send_file, send_from_directory
import google.generativeai as geai

app = Flask(__name__)

# Secret key for session management
app.secret_key = 'SpeechProject'

# Folder for storing uploaded audio files
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max file size set to 16 MB

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Configure Generative AI API Key
geai.configure(api_key=GEMINI_API_KEY)  # Replace with your actual API key

# Function to check if file type is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Get all uploaded files
def get_files():
    return sorted([f for f in os.listdir(UPLOAD_FOLDER) if allowed_file(f)], reverse=True)

@app.route('/')
def index():
    return render_template('index.html', files=get_files())

# Function to process audio using Gemini AI
def analyze_audio_with_llm(audio_content):
    model = geai.GenerativeModel("gemini-1.5-pro")

    # Convert audio to Base64 string
    encoded_audio = base64.b64encode(audio_content).decode("utf-8")

    # Send to Gemini API for processing
    prompt = """
    You are an AI that transcribes speech and analyzes sentiment.
    - First, transcribe the given audio into text.
    - Then, provide only the sentiment analysis summary (positive, negative, or neutral).
    
    Format the response as:
    Transcription: <transcribed text>
    Sentiment: <sentiment result>
    """

    response = model.generate_content([
        prompt,
        {"mime_type": "audio/wav", "data": encoded_audio}
    ])

    # Extract response text
    result_text = response.text.strip() if response and response.text else "Error processing transcription"

    # Extract transcription and sentiment properly
    transcript = "No transcription available."
    sentiment = "No sentiment analysis available."

    if "Transcription:" in result_text and "Sentiment:" in result_text:
        try:
            parts = result_text.split("Sentiment:")
            transcript = parts[0].replace("Transcription:", "").strip()
            sentiment = parts[1].strip()
        except IndexError:
            pass

    return transcript, sentiment

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio file provided.')
        return redirect('/')

    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file.')
        return redirect('/')

    if not allowed_file(file.filename):
        flash('Invalid file type. Only .wav files are allowed.')
        return redirect('/')

    # Save file with timestamped name
    timestamped_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], timestamped_filename)
    file.save(file_path)

    try:
        # Read audio file
        with io.open(file_path, 'rb') as audio_file:
            content = audio_file.read()

        # Get transcription and sentiment
        transcript, sentiment = analyze_audio_with_llm(content)

        # Save transcript and sentiment to separate files
        transcript_filename = timestamped_filename.replace('.wav', '.txt')
        sentiment_filename = timestamped_filename.replace('.wav', '_sentiment.txt')

        with open(os.path.join(app.config['UPLOAD_FOLDER'], transcript_filename), 'w') as f:
            f.write(transcript)

        with open(os.path.join(app.config['UPLOAD_FOLDER'], sentiment_filename), 'w') as f:
            f.write(sentiment)

        flash(f"Transcription and Sentiment analysis successful! Files saved as: {transcript_filename} & {sentiment_filename}")
    except Exception as e:
        flash(f"Error during processing: {e}")
        return redirect('/')

    return redirect('/')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/script.js', methods=['GET'])
def scripts_js():
    return send_file('./script.js')

if __name__ == '__main__':
    app.run(debug=True)

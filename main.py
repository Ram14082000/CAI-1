from datetime import datetime
import io
import os
from google.cloud import speech
from google.cloud import texttospeech_v1
from google.cloud import language_v1
from flask import Flask, flash, render_template, request, redirect, url_for, send_file, send_from_directory
#from werkzeug.utils import secure_filename

app = Flask(__name__)

# Set the secret key to a random, unique value
app.secret_key = 'SpeechProject'

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit to 16 MB

# Configure TTS folder
TTS_FOLDER = 'tts'
ALLOWED_EXTENSIONS = {'wav'}
app.config['TTS_FOLDER'] = TTS_FOLDER

os.makedirs(TTS_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if allowed_file(filename):
            files.append(filename)
            print(filename)
    files.sort(reverse=True)
    return files

@app.route('/')
def index():
    files = get_files()
    tts_files = get_tts_files()  # Fetch synthesized TTS files
    return render_template('index.html', files=files, tts_files=tts_files)

def get_tts_files():
    tts_folder = 'tts'
    files = []
    if os.path.exists(tts_folder):
        for filename in os.listdir(tts_folder):
            if filename.endswith('.wav'):
                files.append(filename)
    files.sort(reverse=True)
    return files



speech_client = speech.SpeechClient()

def sample_recognize(content):
    audio = speech.RecognitionAudio(content=content)

    config = speech.RecognitionConfig(
        language_code="en-US",
        model="latest_long",
        audio_channel_count=1,
        enable_word_confidence=True,
        enable_word_time_offsets=True,
    )

    try:
        # Perform the asynchronous long-running recognition
        operation = speech_client.long_running_recognize(config=config, audio=audio)
        response = operation.result(timeout=90)

        # Compile the transcript from the response
        txt = ''
        for result in response.results:
            txt += result.alternatives[0].transcript + '\n'
        return txt
    except Exception as e:
        print(f"Error during Speech-to-Text recognition: {e}")
        raise e

text_client = texttospeech_v1.TextToSpeechClient()

def sample_synthesize_speech(text=None, ssml=None, output_filename="output.wav"):
    if not text and not ssml:
        raise ValueError("Either 'text' or 'ssml' must be provided.")

    # Prepare input
    if ssml:
        synthesis_input = texttospeech_v1.SynthesisInput(ssml=ssml)
    else:
        synthesis_input = texttospeech_v1.SynthesisInput(text=text)

    # Voice settings
    voice = texttospeech_v1.VoiceSelectionParams(
        language_code="en-UK",
        ssml_gender=texttospeech_v1.SsmlVoiceGender.FEMALE
    )

    # Audio configuration
    audio_config = texttospeech_v1.AudioConfig(
        audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16
    )

    # Make the API request
    try:
        response = text_client.synthesize_speech(
            request=texttospeech_v1.SynthesizeSpeechRequest(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
        )
        # Save the audio content to a file
        with open(output_filename, "wb") as out:
            out.write(response.audio_content)
        print(f"Audio content written to '{output_filename}'")

        return response.audio_content

    except Exception as e:
        print(f"Error during synthesis: {e}")
        return None

language_client = language_v1.LanguageServiceClient()

def analyze_sentiment(text):
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    response = language_client.analyze_sentiment(request={"document": document})
    sentiment_score = response.document_sentiment.score

    if sentiment_score > 0.2:
        return "positive"
    elif sentiment_score < -0.2:
        return "negative"
    else:
        return "neutral"

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio file provided.')
        return redirect('/')
    
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file.')
        return redirect('/')
    
    # Validate file type
    if not allowed_file(file.filename):
        flash('Invalid file type. Only .wav files are allowed.')
        return redirect('/')
    
    # Save the uploaded file
    #filename = secure_filename(file.filename)
    timestamped_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], timestamped_filename)
    file.save(file_path)
    print(f"File saved at: {file_path}")

    # Read and process the saved audio file
    try:
        with io.open(file_path, 'rb') as audio_file:
            content = audio_file.read()

        # Call the Speech-to-Text function
        transcript = sample_recognize(content)

        sentiment = analyze_sentiment(transcript)

        # Save the transcript as a .txt file
        transcript_filename = timestamped_filename.replace('.wav', '.txt')
        transcript_path = os.path.join(app.config['UPLOAD_FOLDER'], transcript_filename)

        sentiment_filename = transcript_filename.replace('.txt', '_sentiment.txt')
        sentiment_path=os.path.join(app.config['UPLOAD_FOLDER'], sentiment_filename)

        with open(transcript_path, 'w') as transcript_file:
            transcript_file.write(transcript)

        with open(sentiment_path, 'w') as sentiment_file:
            sentiment_file.write(sentiment)


        flash(f"Transcription successful! Transcript saved as: {transcript_filename}")
    except Exception as e:
        flash(f"Error during transcription: {e}")
        return redirect('/')

    return redirect('/')
 
@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']

    if not text:
        flash("No text provided for synthesis.")
        return redirect('/')

    # Define the output file path
    #os.makedirs(app.config['TTS_FOLDER'], exist_ok=True)
    text_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.txt'

    output_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'

    sentiment_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '_sentiment.txt'

    output_filepath = os.path.join(app.config['TTS_FOLDER'], output_filename)
    text_filepath = os.path.join(app.config['TTS_FOLDER'], text_filename)
    sentiment_filepath = os.path.join(app.config['TTS_FOLDER'], sentiment_filename)

    # Use the sample_synthesize_speech function
    try:
        with open(text_filepath, 'w') as text_file:
            text_file.write(text)

        sentiment = analyze_sentiment(text)

        with open(sentiment_filepath, 'w') as sentiment_file:
            sentiment_file.write(sentiment)
        
        audio_content = sample_synthesize_speech(text=text, output_filename=output_filepath)
        if audio_content:
            flash(f"Audio file created: {output_filename}, Text file created: {text_filename}")
        else:
            flash("Error occurred during audio synthesis.")
    except Exception as e:
        flash(f"Error during synthesis: {e}")

    return redirect('/')  # Redirect back to the main page


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/tts/<filename>')
def serve_tts_file(filename):
    # Corrected the key to 'TTS_FOLDER'
    return send_from_directory(app.config['TTS_FOLDER'], filename)

@app.route('/uploads/<filename>')
def get_file(filename):
    return send_file(filename)

@app.route('/script.js',methods=['GET'])
def scripts_js():
    return send_file('./script.js')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)

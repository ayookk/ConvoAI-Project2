from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, flash
from werkzeug.utils import secure_filename
from google.cloud import speech
from google.cloud import texttospeech
from google.cloud import language_v1
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "f4038a415f02b19abf3a6376f9ed40ae3ad13a6d"  # Replace with your secret key

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def analyze_sentiment(text):
    """
    Analyze text sentiment using Google Cloud Language API
    """
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)

    try:
        sentiment = client.analyze_sentiment(request={'document': document}).document_sentiment
        score = sentiment.score
        magnitude = sentiment.magnitude

        # Determine sentiment category
        if score > 0.1:
            category = "POSITIVE"
        elif score < -0.1:
            category = "NEGATIVE"
        else:
            category = "NEUTRAL"

        return {
            'category': category,
            'score': score,
            'magnitude': magnitude
        }
    except Exception as e:
        print(f"Error in sentiment analysis: {e}")
        return None


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith('.wav'):
            base_name = filename.rsplit('.', 1)[0]
            transcript_file = base_name + '.txt'
            sentiment_file = base_name + '_sentiment.txt'

            # Check if the transcript and sentiment files exist
            transcript_exists = os.path.exists(os.path.join(UPLOAD_FOLDER, transcript_file))
            sentiment_exists = os.path.exists(os.path.join(UPLOAD_FOLDER, sentiment_file))

            file_info = {
                'audio': filename,
                'transcript': transcript_file if transcript_exists else None,
                'sentiment': sentiment_file if sentiment_exists else None
            }
            files.append(file_info)

    # Sort by audio filename in reverse order
    return sorted(files, key=lambda x: x['audio'], reverse=True)


def transcribe_audio(file_path):
    """
    Transcribe audio file using Google Cloud Speech-to-Text
    """
    client = speech.SpeechClient()

    with open(file_path, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=48000,
        language_code="en-US",
        audio_channel_count=1,
        enable_automatic_punctuation=True
    )

    try:
        response = client.recognize(config=config, audio=audio)
        if response.results:
            return response.results[0].alternatives[0].transcript
        return "No speech detected"
    except Exception as e:
        print(f"Error in transcription: {e}")
        return f"Error in transcription: {str(e)}"


def synthesize_text(text):
    """
    Convert text to speech using Google Cloud Text-to-Speech
    """
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        name="en-US-Standard-C"
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        speaking_rate=1.0,
        pitch=0.0,
        sample_rate_hertz=24000
    )

    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        return response.audio_content
    except Exception as e:
        print(f"Error in text-to-speech: {e}")
        return None


@app.route('/')
def index():
    files = get_files()
    return render_template('index.html', files=files)


@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)

    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        # Save the audio file
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Transcribe the audio
        transcript = transcribe_audio(file_path)

        # Save the transcript
        txt_filename = filename.rsplit('.', 1)[0] + '.txt'
        txt_path = os.path.join(app.config['UPLOAD_FOLDER'], txt_filename)
        with open(txt_path, 'w') as f:
            f.write(transcript)

        # Analyze and save sentiment
        sentiment = analyze_sentiment(transcript)
        if sentiment:
            sentiment_filename = filename.rsplit('.', 1)[0] + '_sentiment.txt'
            sentiment_path = os.path.join(app.config['UPLOAD_FOLDER'], sentiment_filename)
            with open(sentiment_path, 'w') as f:
                f.write(f"Category: {sentiment['category']}\n")
                f.write(f"Score: {sentiment['score']:.2f}\n")
                f.write(f"Magnitude: {sentiment['magnitude']:.2f}\n")

        return redirect('/')

    return redirect('/')


@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']
    if not text:
        flash('No text provided')
        return redirect('/')

    # Generate audio from text
    audio_content = synthesize_text(text)
    if audio_content:
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(file_path, 'wb') as f:
            f.write(audio_content)

        # Save the original text
        txt_filename = filename.rsplit('.', 1)[0] + '.txt'
        txt_path = os.path.join(app.config['UPLOAD_FOLDER'], txt_filename)
        with open(txt_path, 'w') as f:
            f.write(text)

        # Analyze and save sentiment
        sentiment = analyze_sentiment(text)
        if sentiment:
            sentiment_filename = filename.rsplit('.', 1)[0] + '_sentiment.txt'
            sentiment_path = os.path.join(app.config['UPLOAD_FOLDER'], sentiment_filename)
            with open(sentiment_path, 'w') as f:
                f.write(f"Category: {sentiment['category']}\n")
                f.write(f"Score: {sentiment['score']:.2f}\n")
                f.write(f"Magnitude: {sentiment['magnitude']:.2f}\n")
    else:
        flash('Error generating audio')

    return redirect('/')


@app.route('/script.js')
def scripts_js():
    return send_file('./script.js')


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
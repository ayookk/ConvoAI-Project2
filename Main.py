from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, flash
from werkzeug.utils import secure_filename
import os
from google.cloud import speech, texttospeech, language_v1

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Added secret key for flash messages

# Configure upload folders
UPLOAD_FOLDER = 'uploads'
TTS_FOLDER = 'tts'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)

# Initialize Google Cloud clients
client_speech = speech.SpeechClient()
client_tts = texttospeech.TextToSpeechClient()
client_language = language_v1.LanguageServiceClient()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'wav'

def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith('.wav'):
            base_name = filename.rsplit('.', 1)[0]
            transcript_file = base_name + '.txt'
            file_info = {
                'audio': filename,
                'transcript': transcript_file if os.path.exists(os.path.join(UPLOAD_FOLDER, transcript_file)) else None
            }
            files.append(file_info)
    return sorted(files, key=lambda x: x['audio'], reverse=True)

def transcribe_audio(file_path):
    with open(file_path, 'rb') as audio_file:
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
        response = client_speech.recognize(config=config, audio=audio)
        if response.results:
            return response.results[0].alternatives[0].transcript
        return "No speech detected"
    except Exception as e:
        print(f"Error in transcription: {e}")
        return f"Error in transcription: {str(e)}"

def analyze_sentiment(text):
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    try:
        sentiment = client_language.analyze_sentiment(request={'document': document}).document_sentiment
        score = sentiment.score
        magnitude = sentiment.magnitude
        
        # More detailed sentiment analysis
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

def synthesize_text(text):
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
        response = client_tts.synthesize_speech(
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
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        # Transcribe the audio
        transcript = transcribe_audio(file_path)
        
        # Save the transcript
        txt_filename = filename.rsplit('.', 1)[0] + '.txt'
        txt_path = os.path.join(UPLOAD_FOLDER, txt_filename)
        
        # Analyze sentiment
        sentiment = analyze_sentiment(transcript)
        if sentiment:
            with open(txt_path, 'w') as f:
                f.write(f"Transcript:\n{transcript}\n\n")
                f.write(f"Sentiment Analysis:\n")
                f.write(f"Category: {sentiment['category']}\n")
                f.write(f"Score: {sentiment['score']:.2f}\n")
                f.write(f"Magnitude: {sentiment['magnitude']:.2f}\n")
        else:
            with open(txt_path, 'w') as f:
                f.write(f"Transcript:\n{transcript}\n")

        return redirect('/')

    return redirect('/')

@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form.get('text')
    if not text:
        flash('No text provided')
        return redirect('/')

    # Generate audio from text
    audio_content = synthesize_text(text)
    if audio_content:
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, 'wb') as f:
            f.write(audio_content)

        # Analyze and save sentiment
        sentiment = analyze_sentiment(text)
        txt_filename = filename.rsplit('.', 1)[0] + '.txt'
        txt_path = os.path.join(UPLOAD_FOLDER, txt_filename)
        
        if sentiment:
            with open(txt_path, 'w') as f:
                f.write(f"Original Text:\n{text}\n\n")
                f.write(f"Sentiment Analysis:\n")
                f.write(f"Category: {sentiment['category']}\n")
                f.write(f"Score: {sentiment['score']:.2f}\n")
                f.write(f"Magnitude: {sentiment['magnitude']:.2f}\n")
        else:
            with open(txt_path, 'w') as f:
                f.write(f"Original Text:\n{text}\n")
    else:
        flash('Error generating audio')

    return redirect('/')

@app.route('/script.js')
def scripts_js():
    return send_file('./script.js')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

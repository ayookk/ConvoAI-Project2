from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, send_file, flash
from werkzeug.utils import secure_filename
import os
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Google Cloud APIs with simplified imports
from google.cloud import speech
from google.cloud import language_v1 as language

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Create uploads folder if it doesn't exist
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['wav', 'webm', 'mp3']

def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith(('.wav', '.webm', '.mp3')):
            base_name = filename.rsplit('.', 1)[0]
            transcript_file = base_name + '.txt'
            file_info = {
                'audio': filename,
                'transcript': transcript_file if os.path.exists(os.path.join(UPLOAD_FOLDER, transcript_file)) else None
            }
            files.append(file_info)
    return sorted(files, key=lambda x: x['audio'], reverse=True)

def process_audio(file_path):
    """Process audio file with Google's Speech-to-Text and Natural Language APIs"""
    try:
        # Initialize the Speech-to-Text client
        speech_client = speech.SpeechClient()
        
        # Read audio file
        with open(file_path, 'rb') as audio_file:
            content = audio_file.read()
        
        # Configure speech recognition request
        audio = speech.RecognitionAudio(content=content)
        
        # For WEBM OPUS audio from browser, use the appropriate config
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            # Don't specify sample_rate_hertz to let the API detect it
            language_code="en-US",
            enable_automatic_punctuation=True,
            audio_channel_count=1,  # Mono audio from browser recording
        )
        
        # Perform speech recognition
        logger.info("Sending audio to Speech-to-Text API")
        response = speech_client.recognize(config=config, audio=audio)
        logger.info(f"Received response from Speech-to-Text API")
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
        
        transcript = transcript.strip()
        logger.info(f"Transcribed text: {transcript}")
        
        # Perform sentiment analysis if we have a transcript
        sentiment = "No sentiment analysis available."
        if transcript:
            # Initialize the Natural Language API client
            language_client = language.LanguageServiceClient()
            
            # Prepare the document
            document = language.Document(
                content=transcript,
                type_=language.Document.Type.PLAIN_TEXT
            )
            
            # Analyze sentiment
            logger.info("Sending text to Natural Language API for sentiment analysis")
            sentiment_response = language_client.analyze_sentiment(document=document)
            sentiment_score = sentiment_response.document_sentiment.score
            sentiment_magnitude = sentiment_response.document_sentiment.magnitude
            
            # Interpret sentiment
            if sentiment_score > 0.25:
                sentiment_label = "Positive"
            elif sentiment_score < -0.25:
                sentiment_label = "Negative"
            else:
                sentiment_label = "Neutral"
                
            sentiment = f"Sentiment: {sentiment_label}\nScore: {sentiment_score:.2f}\nMagnitude: {sentiment_magnitude:.2f}"
            logger.info(f"Sentiment analysis result: {sentiment}")
        
        return transcript, sentiment
        
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}", exc_info=True)
        return f"Error processing audio: {str(e)}", "Error in sentiment analysis"

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
    
    # Save the file
    try:
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        logger.info(f"Audio file saved at: {file_path}")
        
        # Process the audio
        transcript, sentiment = process_audio(file_path)
        
        # Save the transcript and sentiment
        if transcript:
            txt_filename = filename.rsplit('.', 1)[0] + '.txt'
            txt_path = os.path.join(UPLOAD_FOLDER, txt_filename)
            
            with open(txt_path, 'w') as f:
                f.write(f"Transcript:\n{transcript}\n\n")
                if sentiment:
                    f.write(f"Sentiment Analysis:\n{sentiment}\n")
            
            logger.info(f"Transcript and sentiment saved to: {txt_path}")
        
        return redirect('/')
    
    except Exception as e:
        logger.error(f"Error in upload_audio: {str(e)}", exc_info=True)
        flash(f"Error: {str(e)}")
        return redirect('/')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/script.js')
def serve_script():
    return send_file('script.js')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)  # Set debug to False for production
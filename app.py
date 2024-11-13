from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial
from twilio.rest import Client
from dotenv import load_dotenv
import os
import logging
import requests
import tempfile
from openai import OpenAI


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)


# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Twilio client
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

@app.route('/')
def index():
    return "Voice Meeting Summarizer is running!"

@app.route('/join-conference', methods=['POST'])
def join_conference():
    """Handle incoming calls and add them to conference"""
    logger.info("========= Conference Joined =========")
    response = VoiceResponse()
    
    # Create a dial element
    dial = Dial()
    
    dial.conference(
        'MeetingRoom',
        startConferenceOnEnter="true",      # Correct attribute name
        endConferenceOnExit="true",        # Correct attribute name
        record=True,
        recordingStatusCallback='https://voice-meeting-summarizer.onrender.com/recording-callback',
        recordingStatusCallbackEvent='in-progress completed',
        recordingStatusCallbackMethod='POST',
        statusCallback='https://voice-meeting-summarizer.onrender.com/conference-status',
        statusCallbackEvent='start end join leave',
        statusCallbackMethod='POST',
        waitUrl='http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical',
        beep=True,
        muted=False
    )
    
    logger.info("Generated TwiML: %s", str(response))
    
    response.append(dial)
    return Response(str(response), mimetype='text/xml')

@app.route('/recording-callback', methods=['POST'])
def recording_callback():
    """Handle recording status callbacks"""
    
    logger.info("========= Recording Callback Received =========")
    
    # Log all incoming data from Twilio
    logger.info(f"All callback data: {request.values.to_dict()}")
    
    recording_url = request.values.get('RecordingUrl')
    recording_sid = request.values.get('RecordingSid')
    recording_status = request.values.get('RecordingStatus')  # Added this
    
    logger.info(f"Recording Status: {recording_status}")
    logger.info(f"Recording URL: {recording_url}")
    logger.info(f"Recording SID: {recording_sid}")
    
    # More detailed logging
    if recording_url:
        logger.info("Recording URL received successfully")
    else:
        logger.warning("No recording URL in callback")
        
    logger.info("========= Recording Callback Completed =========")
    
    return "OK"

@app.route('/conference-status', methods=['POST'])
def conference_status():
    """Handle conference status callbacks"""
    logger.info("========= Conference Status =========")
    conference_sid = request.values.get('ConferenceSid')
    event_type = request.values.get('StatusCallbackEvent')
    
    return "OK"


@app.route('/test-transcription', methods=['GET'])
def test_transcription():
    """Test endpoint with mock recording data"""
    mock_recording_data = {
        'RecordingSid': 'RE123456789',
        # Use a publicly accessible audio URL for testing
        'RecordingUrl': 'https://github.com/CompVis/latent-diffusion/raw/main/data/inpainting_examples/overture.mp3',
        'RecordingStatus': 'completed',
        'RecordingDuration': '30'
    }
    
    return process_recording(mock_recording_data)

def process_recording(recording_data):
    """Process recording data and prepare for OpenAI"""
    try:
        logger.info(f"Processing recording: {recording_data['RecordingSid']}")
        
        # Download the audio file
        response = requests.get(recording_data['RecordingUrl'])
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name
        
        # Transcribe with Whisper
        with open(temp_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            
        logger.info(" ==== transcript ====", transcript)
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        return {
            "status": "success",
            "message": "Recording processed successfully",
            "recording_sid": recording_data['RecordingSid'],
            "transcript": transcript.text
        }
        
    except Exception as e:
        logger.error(f"Error processing recording: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
        
def test_openai_connection():
    """Test OpenAI API connection"""
    try:
        # Simple test completion
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": "Hello, this is a test!"}
            ]
        )
        return True, "OpenAI connection successful"
    except Exception as e:
        return False, f"OpenAI connection failed: {str(e)}"

@app.route('/test-openai', methods=['GET'])
def test_openai():
    """Test endpoint for OpenAI connection"""
    success, message = test_openai_connection()
    return {
        "success": success,
        "message": message
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5005))
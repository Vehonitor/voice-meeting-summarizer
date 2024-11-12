from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial
from twilio.rest import Client
from dotenv import load_dotenv
import os
import logging


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

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
    
    # Add participant to conference
    dial.conference(
        'MeetingRoom',
        record='record-from-start',
        recordingStatusCallback='/recording-callback',
        statusCallback='/conference-status',
        statusCallbackEvent=['start', 'end', 'join', 'leave'],
        waitUrl='http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical'
    )
    
    response.append(dial)
    return Response(str(response), mimetype='text/xml')

@app.route('/recording-callback', methods=['POST'])
def recording_callback():
    """Handle recording status callbacks"""
    recording_url = request.values.get('RecordingUrl')
    recording_sid = request.values.get('RecordingSid')
    
    logger.info("recording url", recording_url)
    print(f"Recording completed: {recording_sid}")
    print(f"Recording URL: {recording_url}")
    
    return "OK"

@app.route('/conference-status', methods=['POST'])
def conference_status():
    """Handle conference status callbacks"""
    conference_sid = request.values.get('ConferenceSid')
    event_type = request.values.get('StatusCallbackEvent')
    
    print(f"Conference {conference_sid} event: {event_type}")
    
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5005))
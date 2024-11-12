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
        record=True,
        # record='record-from-start',
        recordingStatusCallback='https://voice-meeting-summarizer.onrender.com/recording-callback',
        recordingStatusCallbackEvent='in-progress completed',
        statusCallback='https://voice-meeting-summarizer.onrender.com/conference-status',
        statusCallbackEvent='start end join leave',
        waitUrl='http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical',
        recording_status_callback_method='POST',
        recording_status_callback_event='in-progress completed absent',
        recording_channels='mono',
    )
    
    response.append(dial)
    return Response(str(response), mimetype='text/xml')

@app.route('/recording-callback', methods=['POST'])
def recording_callback():
    """Handle recording status callbacks"""
    
    logger.info("========= About to process conference recording =========")
    logger.info(f"All callback data: {request.values.to_dict()}")
    recording_url = request.values.get('RecordingUrl')
    recording_sid = request.values.get('RecordingSid')
    
    logger.info("recording url", recording_url)
    logger.info("recording sid", recording_sid)
    print(f"Recording completed: {recording_sid}")
    print(f"Recording URL: {recording_url}")
    
    return "OK"

@app.route('/conference-status', methods=['POST'])
def conference_status():
    """Handle conference status callbacks"""
    logger.info("========= Conference Status =========")
    conference_sid = request.values.get('ConferenceSid')
    event_type = request.values.get('StatusCallbackEvent')
    
    print(f"Conference {conference_sid} event: {event_type}")
    
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5005))
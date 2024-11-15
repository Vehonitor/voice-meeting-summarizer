from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial
from twilio.rest import Client
from dotenv import load_dotenv
import os
import logging
import requests
import tempfile
from openai import OpenAI
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)


# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
# openai.api_key = os.getenv('OPENAI_API_KEY')


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
    dial = Dial()
    
    # Simplified conference setup
    dial.conference(
        'MeetingRoom',
        record=True,
        startConferenceOnEnter=True,
        endConferenceOnExit=False,
        recordingStatusCallback='https://voice-meeting-summarizer.onrender.com/recording-callback',
        recordingStatusCallbackMethod='POST',
        recordingStatusCallbackEvent='in-progress completed',
        beep=True,
        statusCallback='https://voice-meeting-summarizer.onrender.com/conference-status',
        statusCallbackEvent='start end join leave',
        statusCallbackMethod='POST'
    )
    
    response.append(dial)
    return Response(str(response), mimetype='text/xml')

@app.route('/recording-callback', methods=['POST'])
def recording_callback():
    """Handle Twilio recording callback"""
    logger.info("========= Recording Callback Received =========")
    
    recording_status = request.values.get('RecordingStatus')
    recording_url = request.values.get('RecordingUrl')
    recording_sid = request.values.get('RecordingSid')
    
    logger.info(f"Recording Status: {recording_status}, Recording SID: {recording_sid}")
    
    # Only proceed if the recording is completed
    if recording_status != 'completed':
        logger.info(f"Recording status is {recording_status}. Waiting for completion.")
        return "OK"
    
    # Download the recording file
    try:
        logger.info(f"Downloading recording from: {recording_url}")
        auth = (os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
        response = requests.get(recording_url, auth=auth)
        response.raise_for_status()
        
        # Save the recording to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name
            logger.info(f"Audio saved to temporary file: {temp_file_path}")
    
    except Exception as e:
        logger.error(f"Error downloading recording: {str(e)}")
        return "Error downloading recording", 500
    
    # Step 1: Transcribe the audio using Whisper
    try:
        logger.info("Transcribing with Whisper...")
        with open(temp_file_path, "rb") as audio_file:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
                response_format="text"
            )
        
        if not transcript_response:
            raise Exception("No transcription result returned.")
        
        transcript_text = transcript_response.strip()
        logger.info(f"Transcription result: {transcript_text}")
    
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        return "Error transcribing audio", 500
    
    finally:
        # Step 2: Cleanup - Delete the temporary audio file
        try:
            os.unlink(temp_file_path)
            logger.info("Temporary audio file deleted.")
        except Exception as cleanup_error:
            logger.error(f"Error deleting temporary file: {str(cleanup_error)}")
    
    # Step 3: Generate a summary using GPT
    try:
        logger.info("Generating summary with GPT...")
        summary_response = client.chat.completions.create(
            model="gpt-4",
             messages=[
        {"role": "system", "content": "You are a helpful assistant that summarizes conversations accurately."},
        {"role": "user", "content": f"Summarize the following text in a concise manner:\n\n{transcript_text}"}
    ],
            max_tokens=100,
            temperature=0.5
        )
        
        summary = summary_response.choices[0].message.content.strip()
        logger.info(f"Generated summary: {summary}")
    
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return "Error generating summary", 500

    # Step 4: Log the final output and return success
    logger.info("========= Recording Processing Complete =========")
    logger.info(f"Recording SID: {recording_sid}")
    logger.info(f"Transcript: {transcript_text}")
    logger.info(f"Summary: {summary}")
    
    try:
        # After getting transcript and summary
        send_meeting_summary(transcript_text, summary, recording_sid)
        logger.info("========= Recording Processing Complete =========")
        
    except Exception as e:
        logger.error(f"Error in recording callback: {str(e)}")
    
    # return "OK"

    return {
        "status": "success",
        "recording_sid": recording_sid,
        "transcript": transcript_text,
        "summary": summary
    }, 200

@app.route('/conference-status', methods=['POST'])
def conference_status():
    """Handle conference status callbacks"""
    logger.info("========= Conference Status =========")
    conference_sid = request.values.get('ConferenceSid')
    event_type = request.values.get('StatusCallbackEvent')
    
    return "OK"
        
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


def send_meeting_summary(transcript, summary, recording_sid):
    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        
        # HTML Email Template
        html_content = f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background-color: #4a54f1;
                        color: white;
                        padding: 20px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                    }}
                    .section {{
                        background-color: #f9f9f9;
                        padding: 20px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                        border: 1px solid #eee;
                    }}
                    .recording-id {{
                        color: #fff;
                        font-size: 0.9em;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Meeting Summary</h1>
                    <div class="recording-id">Recording ID: {recording_sid}</div>
                </div>
                
                <div class="section">
                    <h2>Summary</h2>
                    <p>{summary}</p>
                </div>
                
                <div class="section">
                    <h2>Full Transcript</h2>
                    <p>{transcript}</p>
                </div>
                
                <div style="color: #666; font-size: 0.8em; text-align: center; margin-top: 20px;">
                    Generated by Voice Meeting Summarizer
                </div>
            </body>
        </html>
        """
        
        recipients = get_meeting_participants()
        
        message = Mail(
            from_email=os.getenv('SENDGRID_FROM_EMAIL'),
            to_emails=recipients,
            subject='Your Meeting Summary',
            html_content=html_content
        )

        response = sg.send(message)
        logger.info(f"Email sent successfully to {len(recipients)} recipients")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False
    
def get_meeting_participants():
    recipients = os.getenv('MEETING_RECIPIENTS', '').split(',')
    if not recipients:
        # Fallback to default recipient
        recipients = [os.getenv('DEFAULT_RECIPIENT_EMAIL')]
    return recipients

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5005))
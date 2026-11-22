from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

class ParentInquiryForm(FlaskForm):
    """Parent message/inquiry submission to assigned Warden"""
    subject = StringField('Subject / Inquiry Topic', validators=[
        DataRequired(message='Please provide an inquiry subject.'),
        Length(min=3, max=150, message='Subject must be between 3 and 150 characters.')
    ])
    message = TextAreaField('Detailed Message / Inquiry', validators=[
        DataRequired(message='Please provide message details.'),
        Length(min=10, max=2000, message='Message must be between 10 and 2000 characters.')
    ])
    submit = SubmitField('Submit Inquiry to Warden')


class WardenReplyInquiryForm(FlaskForm):
    """Warden response to parent inquiry"""
    response = TextAreaField('Official Warden Response', validators=[
        DataRequired(message='Please provide a response before submitting.'),
        Length(min=5, max=2000, message='Response must be between 5 and 2000 characters.')
    ])
    status = SelectField('Inquiry Status', choices=[
        ('In Progress', 'In Progress / Under Review'),
        ('Resolved', 'Resolved / Addressed')
    ], default='Resolved')
    submit = SubmitField('Send Response')


class AdminCreateParentForm(FlaskForm):
    """Administrator form to create and link a Parent User account"""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=50, message='Username must be 3-50 characters.')
    ])
    email = StringField('Email Address', validators=[
        DataRequired(),
        Email(message='Valid email address is required.')
    ])
    password = PasswordField('Initial Temporary Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters.')
    ])
    parent_name = StringField('Parent / Guardian Full Name', validators=[
        DataRequired(),
        Length(max=100)
    ])
    phone_number = StringField('Contact Phone Number', validators=[
        DataRequired(),
        Length(min=10, max=15, message='Valid phone number (10-15 digits) required.')
    ])
    relationship_to_student = SelectField('Relationship to Student', choices=[
        ('Father', 'Father'),
        ('Mother', 'Mother'),
        ('Legal Guardian', 'Legal Guardian'),
        ('Other', 'Other')
    ], default='Father')
    student_id = SelectField('Link to Student (Resident)', coerce=int, validators=[
        DataRequired(message='Please select a student to link.')
    ])
    account_status = SelectField('Account Status', choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], default='active')
    submit = SubmitField('Create & Link Parent Account')


class AdminEditParentForm(FlaskForm):
    """Administrator form to edit parent profile and link"""
    parent_name = StringField('Parent / Guardian Full Name', validators=[
        DataRequired(),
        Length(max=100)
    ])
    phone_number = StringField('Contact Phone Number', validators=[
        DataRequired(),
        Length(min=10, max=15)
    ])
    relationship_to_student = SelectField('Relationship to Student', choices=[
        ('Father', 'Father'),
        ('Mother', 'Mother'),
        ('Legal Guardian', 'Legal Guardian'),
        ('Other', 'Other')
    ])
    student_id = SelectField('Linked Student (Resident)', coerce=int, validators=[
        DataRequired()
    ])
    account_status = SelectField('Account Status', choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ])
    submit = SubmitField('Update Parent Profile')


class AdminResetParentPasswordForm(FlaskForm):
    """Administrator form to reset parent password"""
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Reset Password')


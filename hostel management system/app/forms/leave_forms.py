import re
from datetime import date
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, TextAreaField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError, Optional

class ApplyLeaveForm(FlaskForm):
    """Form for students to submit leave applications"""
    leave_type = SelectField('Leave Category', choices=[
        ('Home Visit', 'Home Visit'),
        ('Medical Leave', 'Medical Leave'),
        ('Family Function', 'Family Function'),
        ('Personal Leave', 'Personal Leave'),
        ('Other', 'Other')
    ], validators=[DataRequired(message='Please select a leave category.')])

    from_date = DateField('From Date', format='%Y-%m-%d', validators=[DataRequired(message='Please select the departure date.')])
    to_date = DateField('To Date', format='%Y-%m-%d', validators=[DataRequired(message='Please select the return date.')])
    
    reason = TextAreaField('Reason for Leave', validators=[
        DataRequired(message='Please state the reason for your leave.'),
        Length(min=10, max=1000, message='Reason must be at least 10 characters long.')
    ])
    
    destination = StringField('Destination / Address During Leave', validators=[
        DataRequired(message='Please provide your destination address.'),
        Length(min=5, max=255, message='Destination must be at least 5 characters long.')
    ])
    
    emergency_contact = StringField('Emergency Contact Number', validators=[
        DataRequired(message='Please provide an emergency contact phone number.'),
        Length(min=10, max=15, message='Contact number must be between 10 and 15 digits.')
    ])
    
    supporting_document = FileField('Supporting Document (Optional for Medical/Special Leave)', validators=[
        Optional(),
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg'], 'Allowed file types: PDF, PNG, JPG, JPEG (Max 5MB)')
    ])
    
    submit = SubmitField('Submit Leave Application')

    def validate_from_date(self, field):
        if field.data and field.data < date.today():
            raise ValidationError('Departure date cannot be in the past.')

    def validate_to_date(self, field):
        if self.from_date.data and field.data:
            if field.data < self.from_date.data:
                raise ValidationError('Return date cannot be earlier than departure date.')

    def validate_emergency_contact(self, field):
        if field.data:
            # Allow digits, spaces, hyphens, plus sign
            cleaned = re.sub(r'[\s\-\+\(\)]', '', field.data)
            if not cleaned.isdigit() or len(cleaned) < 10:
                raise ValidationError('Please enter a valid phone number containing at least 10 digits.')


class WardenReviewLeaveForm(FlaskForm):
    """Form for Warden to add review remarks and approve/reject leave"""
    action = SelectField('Action Decision', choices=[
        ('approve', 'Approve Leave'),
        ('reject', 'Reject Leave')
    ], validators=[DataRequired()])
    
    review_comment = TextAreaField('Review Remarks / Reason', validators=[
        Length(max=500, message='Review remarks cannot exceed 500 characters.')
    ])
    
    submit = SubmitField('Submit Review Decision')


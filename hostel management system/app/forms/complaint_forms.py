from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length

class SubmitComplaintForm(FlaskForm):
    """Form for students to file a grievance ticket"""
    title = StringField('Subject / Issue Title', validators=[DataRequired(), Length(min=5, max=150)])
    category = SelectField('Category', choices=[
        ('electrical', 'Electrical (Fan, Light, Switchboard, Geyser)'),
        ('plumbing', 'Plumbing (Tap leakage, Drain blockage, Flush)'),
        ('cleanliness', 'Cleanliness & Housekeeping'),
        ('internet', 'Wi-Fi / LAN Network Connection'),
        ('mess', 'Mess Food & Drinking Water'),
        ('other', 'Discipline / General Infrastructure')
    ], default='electrical', validators=[DataRequired()])
    priority = SelectField('Urgency Priority', choices=[
        ('low', 'Low (Routine observation)'),
        ('medium', 'Medium (Standard maintenance)'),
        ('high', 'High (Urgent attention needed)'),
        ('emergency', 'Emergency (Safety / Water overflow)')
    ], default='medium', validators=[DataRequired()])
    description = TextAreaField('Detailed Issue Description', validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Submit Grievance Ticket')


class ComplaintResponseForm(FlaskForm):
    """Form for Admin/Warden to reply and update grievance ticket status"""
    response_text = TextAreaField('Action Taken / Response Remarks', validators=[DataRequired(), Length(min=5)])
    status = SelectField('Update Ticket Status', choices=[
        ('pending', 'Pending Inspection'),
        ('in_progress', 'In Progress (Technician Assigned)'),
        ('resolved', 'Resolved & Closed')
    ], default='in_progress', validators=[DataRequired()])
    submit = SubmitField('Submit Response & Update Status')


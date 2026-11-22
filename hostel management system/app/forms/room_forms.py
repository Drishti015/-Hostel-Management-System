from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, DecimalField, TextAreaField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from datetime import date

class HostelForm(FlaskForm):
    """Form to add or edit a hostel block"""
    name = StringField('Hostel Block Name', validators=[DataRequired(), Length(max=100)])
    hostel_type = SelectField('Hostel Type', choices=[
        ('boys', 'Boys Hostel'),
        ('girls', 'Girls Hostel'),
        ('co-ed', 'Co-Ed Residence')
    ], validators=[DataRequired()])
    total_floors = IntegerField('Total Number of Floors', default=3, validators=[DataRequired(), NumberRange(min=1, max=20)])
    description = TextAreaField('Description / Facilities', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Save Hostel Block')


class RoomForm(FlaskForm):
    """Form to add or edit a room"""
    hostel_id = SelectField('Hostel Block', coerce=int, validators=[DataRequired()])
    room_number = StringField('Room Number', validators=[DataRequired(), Length(max=20)])
    floor = IntegerField('Floor Number', default=1, validators=[DataRequired(), NumberRange(min=0, max=20)])
    room_type = SelectField('Room Configuration', choices=[
        ('single', 'Single Seater (1 Bed)'),
        ('double', 'Double Seater (2 Beds)'),
        ('triple', 'Triple Seater (3 Beds)'),
        ('four', 'Four Seater (4 Beds)')
    ], default='double', validators=[DataRequired()])
    monthly_fee = DecimalField('Monthly Fee (₹)', default=5000.00, places=2, validators=[DataRequired(), NumberRange(min=0)])
    status = SelectField('Status', choices=[
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance')
    ], default='active', validators=[DataRequired()])
    submit = SubmitField('Save Room & Generate Beds')


class ManualAllocationForm(FlaskForm):
    """Form to manually assign an available bed to an unallocated student"""
    student_id = SelectField('Student', coerce=int, validators=[DataRequired()])
    bed_id = SelectField('Available Bed', coerce=int, validators=[DataRequired()])
    allocated_from = DateField('Allocation Date', default=date.today, validators=[DataRequired()])
    submit = SubmitField('Confirm Bed Allocation')


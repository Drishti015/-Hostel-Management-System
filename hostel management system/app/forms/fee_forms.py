from flask_wtf import FlaskForm
from wtforms import SelectField, DecimalField, DateField, StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from datetime import date

class AddFeePaymentForm(FlaskForm):
    """Form to record hostel fee transactions"""
    student_id = SelectField('Student', coerce=int, validators=[DataRequired()])
    amount = DecimalField('Payment Amount (₹)', places=2, validators=[DataRequired(), NumberRange(min=1.0)])
    payment_date = DateField('Payment Date', default=date.today, validators=[DataRequired()])
    payment_method = SelectField('Payment Method', choices=[
        ('UPI', 'UPI / QR Payment'),
        ('Net Banking', 'Net Banking / NEFT / IMPS'),
        ('Cash', 'Cash Counter'),
        ('Cheque/DD', 'Demand Draft / Cheque')
    ], default='UPI', validators=[DataRequired()])
    transaction_id = StringField('Transaction Ref ID / UTR', validators=[Optional(), Length(max=100)])
    fee_type = SelectField('Fee Category', choices=[
        ('Hostel & Mess Fee', 'Hostel & Mess Fee (Semester)'),
        ('Caution Deposit', 'Caution Money / Security Deposit'),
        ('Room Maintenance Fee', 'Room Maintenance Fee'),
        ('Late Fine / Penalty', 'Late Fine / Disciplinary Penalty')
    ], default='Hostel & Mess Fee', validators=[DataRequired()])
    status = SelectField('Payment Status', choices=[
        ('paid', 'Verified & Paid'),
        ('pending', 'Pending Bank Clearance'),
        ('overdue', 'Overdue')
    ], default='paid', validators=[DataRequired()])
    remarks = TextAreaField('Account Remarks / Notes', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Record Transaction & Generate Receipt')


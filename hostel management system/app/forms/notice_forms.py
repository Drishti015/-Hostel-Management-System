from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length

class NoticeForm(FlaskForm):
    """Form to publish official hostel notices and circulars"""
    title = StringField('Notice Title / Subject', validators=[DataRequired(), Length(min=5, max=200)])
    category = SelectField('Notice Classification', choices=[
        ('announcement', 'General Announcement'),
        ('urgent', 'Urgent / Disciplinary Notice'),
        ('maintenance', 'Facility Maintenance Notice'),
        ('event', 'Hostel / Campus Event')
    ], default='announcement', validators=[DataRequired()])
    target_audience = SelectField('Target Audience', choices=[
        ('all', 'All Hostel Residents & Staff'),
        ('boys', 'Boys Hostel Only'),
        ('girls', 'Girls Hostel Only'),
        ('wardens', 'Wardens & Staff Only')
    ], default='all', validators=[DataRequired()])
    content = TextAreaField('Notice Body Content', validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Publish Notice')


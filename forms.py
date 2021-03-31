from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Regexp

class FinishForm(FlaskForm):
  twitter_username = StringField('twitter_username', validators=[Regexp(r'^[a-zA-Z0-9_]{0,15}$', 0, "Please enter a valid Twitter username (without the @)")])
  spotify_email = HiddenField('spotify_email', validators=[DataRequired()])
  submit = SubmitField('Link My Accounts')  
      
"""
WTForms form definitions for Quiz App.

Contains form classes for:
- Admin login
- Team login/signup
- Game creation
- Round creation
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError


class AdminLoginForm(FlaskForm):
    """Form for admin user login."""

    username = StringField('Username', validators=[
        DataRequired(message='Username is required')
    ])

    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])

    submit = SubmitField('Login')


class TeamLoginForm(FlaskForm):
    """
    Form for team login or signup.

    If team doesn't exist for the game, a new team is created.
    If team exists, password is verified.
    """

    team_name = StringField('Team Name', validators=[
        DataRequired(message='Team name is required'),
        Length(min=2, max=100, message='Team name must be 2-100 characters')
    ])

    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=4, max=100, message='Password must be at least 4 characters')
    ])

    password_confirm = PasswordField('Confirm Password', validators=[
        EqualTo('password', message='Passwords must match')
    ])

    game_code = StringField('Game Code', validators=[
        DataRequired(message='Game code is required'),
        Length(min=6, max=6, message='Game code must be 6 characters')
    ])

    submit = SubmitField('Join Game')

    def validate_game_code(self, field):
        """Validate that game code exists in database."""
        from models import Game
        game = Game.query.filter_by(code=field.data.upper()).first()
        if not game:
            raise ValidationError('Invalid game code')
        if not game.is_active:
            raise ValidationError('This game is no longer active')


class TeamReloginForm(FlaskForm):
    """
    Simpler form for existing team to log back in.

    Used when team is already registered for a game.
    """

    team_name = StringField('Team Name', validators=[
        DataRequired(message='Team name is required')
    ])

    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])

    submit = SubmitField('Login')


class CreateGameForm(FlaskForm):
    """Form for creating a new quiz game."""

    name = StringField('Game Name', validators=[
        DataRequired(message='Game name is required'),
        Length(min=3, max=200, message='Game name must be 3-200 characters')
    ])

    submit = SubmitField('Create Game')


class CreateRoundForm(FlaskForm):
    """Form for creating a new round within a game."""

    name = StringField('Round Name', validators=[
        DataRequired(message='Round name is required'),
        Length(min=2, max=200, message='Round name must be 2-200 characters')
    ])

    submit = SubmitField('Create Round')

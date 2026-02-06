"""
Utility functions for Quiz App.

Contains helper functions for:
- QR code generation
- Unique game code generation
- Text answer validation with regex
- Math-based score calculation
"""
import os
import re
import random
import string
import qrcode
from io import BytesIO


def generate_unique_code(length=6):
    """
    Generate a unique alphanumeric game code.

    Args:
        length: Length of the code (default 6)

    Returns:
        Uppercase alphanumeric string (e.g., 'ABC123')
    """
    # Use uppercase letters and digits, excluding confusing chars (0, O, I, 1, L)
    characters = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(characters) for _ in range(length))


def generate_qr_code(game_code, game_id, base_url='http://localhost:5777'):
    """
    Generate a QR code for a game join URL.

    Creates a QR code image that links to the player join page
    and saves it to the static/qrcodes directory.

    Args:
        game_code: The 6-character game code
        game_id: The database ID of the game
        base_url: Base URL of the application

    Returns:
        Relative path to the saved QR code image
    """
    # Create the join URL
    join_url = f'{base_url}/player/join/{game_code}'

    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(join_url)
    qr.make(fit=True)

    # Create image
    img = qr.make_image(fill_color="black", back_color="white")

    # Ensure directory exists
    qr_dir = os.path.join('static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)

    # Save image
    filename = f'game_{game_id}_{game_code}.png'
    filepath = os.path.join(qr_dir, filename)
    img.save(filepath)

    # Return relative path for database storage
    return f'qrcodes/{filename}'


def validate_text_answer(user_answer, pattern_string):
    """
    Validate user's text answer against regex pattern(s).

    Supports multiple validation modes:
    - Single pattern: Direct regex match (e.g., 'Paris')
    - AND logic with +: 'Paris + Dog' - matches only if ALL patterns match
    - OR logic with |: 'Paris | London' - matches if ANY pattern matches
    - Combined: 'Paris + Dog | Paris + Cat | Bird' - OR of AND groups

    Args:
        user_answer: The answer provided by the user
        pattern_string: Regex pattern(s) to validate against

    Returns:
        bool: True if answer matches pattern, False otherwise

    Examples:
        >>> validate_text_answer("Paris", "Paris")
        True
        >>> validate_text_answer("Paris Dog", "Paris + Dog")
        True
        >>> validate_text_answer("Paris Cat", "Paris + Dog | Paris + Cat")
        True
        >>> validate_text_answer("Bird", "Paris + Dog | Paris + Cat | Bird")
        True
    """
    if not pattern_string or not pattern_string.strip():
        # No pattern = any answer is valid
        return True

    user_answer = str(user_answer).strip()
    pattern_string = pattern_string.strip()

    # Split by | for OR alternatives
    or_groups = [g.strip() for g in pattern_string.split('|')]

    for or_group in or_groups:
        if not or_group:
            continue

        # Split by + for AND requirements within each OR group
        and_patterns = [p.strip() for p in or_group.split('+')]

        # Check if ALL patterns in this AND group match
        all_match = True
        for pattern in and_patterns:
            if pattern and not _match_pattern(user_answer, pattern):
                all_match = False
                break

        # If this OR group matches, return True
        if all_match:
            return True

    return False


def _match_pattern(text, pattern):
    """
    Check if text matches a single regex pattern.

    Args:
        text: Text to match
        pattern: Regex pattern

    Returns:
        bool: True if matches, False otherwise
    """
    try:
        # Case-insensitive by default
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        # Invalid regex pattern - treat as literal string match
        return pattern.lower() in text.lower()


def calculate_math_score(formula, answer_value, other_answers=None):
    """
    Calculate score based on a math formula.

    Safely evaluates mathematical expressions with the user's answer.
    Supports basic arithmetic operations and conditional scoring.

    Args:
        formula: Math formula string (e.g., 'answer * 4', 'answer / 2 + 10')
        answer_value: The numeric answer value to substitute
        other_answers: Optional dict of other question answers for conditional logic

    Returns:
        float: Calculated score, or 0.0 on error

    Examples:
        >>> calculate_math_score("answer * 4", 10)
        40.0
        >>> calculate_math_score("answer / 2 + 10", 20)
        20.0
    """
    if not formula or not formula.strip():
        return 0.0

    try:
        # Convert answer to float
        answer = float(answer_value)
    except (ValueError, TypeError):
        return 0.0

    try:
        # Create safe evaluation context
        safe_context = {
            'answer': answer,
            'abs': abs,
            'min': min,
            'max': max,
            'round': round,
        }

        # Add other answers if provided
        if other_answers:
            for key, value in other_answers.items():
                try:
                    safe_context[key] = float(value)
                except (ValueError, TypeError):
                    safe_context[key] = value

        # Sanitize formula - only allow safe characters
        allowed_chars = set('0123456789.+-*/() answerbsmixround')
        formula_lower = formula.lower()

        # Check for potentially dangerous operations
        dangerous_patterns = ['import', 'exec', 'eval', 'open', 'file', '__']
        for pattern in dangerous_patterns:
            if pattern in formula_lower:
                return 0.0

        # Evaluate formula
        result = eval(formula, {"__builtins__": {}}, safe_context)
        return float(result)

    except (SyntaxError, NameError, TypeError, ZeroDivisionError, ValueError):
        return 0.0
    except Exception:
        # Catch any other unexpected errors
        return 0.0


def calculate_points_for_answer(question_config, answer_text, other_answers=None):
    """
    Calculate points for an answer based on question configuration.

    Args:
        question_config: Dict with question settings including:
            - type: 'text', 'number', or 'radio'
            - validation: Regex pattern for text, formula for number
            - points: Points to award (default 1)
        answer_text: The user's answer
        other_answers: Optional dict of other answers for conditional scoring

    Returns:
        float: Points to award for this answer
    """
    q_type = question_config.get('type', 'text')
    validation = question_config.get('validation', '')
    base_points = question_config.get('points', 1)
    penalty_points = question_config.get('penalty_points', 0)

    if q_type == 'text':
        # Text question - check regex pattern
        if validate_text_answer(answer_text, validation):
            return float(base_points)
        # Wrong answer - apply penalty if answer was attempted
        if answer_text and answer_text.strip() and penalty_points:
            return -float(penalty_points)
        return 0.0

    elif q_type == 'number':
        # Number question - use math formula if provided
        if validation:
            return calculate_math_score(validation, answer_text, other_answers)
        # No formula - just check if it's a valid number
        try:
            float(answer_text)
            return float(base_points)
        except (ValueError, TypeError):
            if answer_text and answer_text.strip() and penalty_points:
                return -float(penalty_points)
            return 0.0

    elif q_type == 'radio':
        # Radio question - check if answer matches correct option
        correct_answer = question_config.get('correct_answer', '')
        if str(answer_text).strip().lower() == str(correct_answer).strip().lower():
            return float(base_points)
        # Wrong answer - apply penalty if answer was attempted
        if answer_text and answer_text.strip() and penalty_points:
            return -float(penalty_points)
        return 0.0

    elif q_type == 'estimate':
        # Estimate question - points based on percentage distance from correct answer
        estimate_config = question_config.get('estimate', {})
        correct_answer = estimate_config.get('correct_answer')
        points_exact = estimate_config.get('points_exact', 4)
        points_10 = estimate_config.get('points_10', 3)
        points_20 = estimate_config.get('points_20', 2)
        points_30 = estimate_config.get('points_30', 1)

        if not answer_text or correct_answer is None:
            return 0.0

        try:
            player_answer = float(answer_text)
            correct_val = float(correct_answer)

            if correct_val == 0:
                # Special case: if correct answer is 0, exact match only
                if player_answer == 0:
                    return float(points_exact)
                return 0.0

            # Calculate percentage difference
            pct_diff = abs(player_answer - correct_val) / abs(correct_val)

            if pct_diff == 0:
                return float(points_exact)
            elif pct_diff <= 0.10:
                return float(points_10)
            elif pct_diff <= 0.20:
                return float(points_20)
            elif pct_diff <= 0.30:
                return float(points_30)
            return 0.0
        except (ValueError, TypeError):
            return 0.0

    # Unknown type
    return 0.0


def apply_round_deduplication(team_id, round_id, questions, Answer):
    """
    Apply duplicate answer deduction for a team's answers in a round.

    If a team gives the same text answer for multiple questions in the same
    round, only the first one (by question order) keeps its points.

    Args:
        team_id: The team's database ID
        round_id: The round's database ID
        questions: List of question config dicts (in order)
        Answer: The Answer model class
    """
    answers = Answer.query.filter_by(team_id=team_id, round_id=round_id).all()
    answer_by_qid = {a.question_id: a for a in answers}

    seen_texts = set()
    for q in questions:
        q_id = q.get('id', '')
        if q.get('type', 'text') != 'text':
            continue
        answer = answer_by_qid.get(q_id)
        if not answer or not answer.answer_text or answer.points <= 0:
            continue
        normalized = answer.answer_text.strip().lower()
        if normalized in seen_texts:
            answer.points = 0
        else:
            seen_texts.add(normalized)

"""
Player routes for Quiz App.

Handles player/team quiz interface and answer submission.
"""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from models import db, Game, Round, Team, Answer, ResubmitPermission
from utils import calculate_points_for_answer
from sqlalchemy import func

bp = Blueprint('player', __name__, url_prefix='/player')


@bp.route('/scoreboard/<game_code>')
def scoreboard(game_code):
    """
    Public scoreboard view for players.

    Scores are hidden per-team when they have submitted answers to a closed round.
    Once game.is_finished is True, scores are revealed for everyone.
    """
    game = Game.query.filter_by(code=game_code.upper()).first_or_404()

    # Check if logged-in team should see hidden scores
    team_id = None
    if current_user.is_authenticated and current_user.get_id().startswith('team_'):
        team_id = int(current_user.get_id().split('_')[1])

    # If game is finished, always show scores
    if game.is_finished:
        return render_template('scoreboard.html', game=game, is_admin=False, team_id=team_id)

    # Check if scores should be hidden for this team
    if team_id:
        # Scores only hidden when team has submitted to the FINAL round (last by order)

        # Get the final round (last by order, excluding parent rounds with children)
        all_rounds = Round.query.filter_by(game_id=game.id).order_by(Round.order.desc()).all()

        # Find the final "leaf" round (one that has no children)
        final_round = None
        for r in all_rounds:
            # Check if this round has children (is a parent)
            has_children = Round.query.filter_by(parent_id=r.id).first() is not None
            if not has_children:
                final_round = r
                break

        if final_round and not final_round.is_open:
            # Final round exists and is closed - check if team submitted to it
            submitted_to_final = Answer.query.filter_by(
                team_id=team_id,
                round_id=final_round.id
            ).first()

            if submitted_to_final:
                # Team has submitted to the final round - hide scores
                return render_template('player/scores_hidden.html', game=game)

    # Show scores
    return render_template('scoreboard.html', game=game, is_admin=False, team_id=team_id)


def team_required(f):
    """
    Decorator to require team authentication.

    Wraps login_required and additionally checks that
    the current user is a Team (not an Admin).
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.get_id().startswith('team_'):
            flash('Please log in as a team to access this page.', 'danger')
            return redirect(url_for('auth.player_login'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/join/<game_code>')
def join_game(game_code):
    """
    Join game page - redirects to login with game code.

    This is the URL in the QR code.
    """
    game = Game.query.filter_by(code=game_code.upper()).first()

    if not game:
        flash('Invalid game code.', 'danger')
        return redirect(url_for('index'))

    if not game.is_active:
        flash('This game is no longer active.', 'danger')
        return redirect(url_for('index'))

    # If already logged in as a team for this game, go to quiz
    if current_user.is_authenticated and current_user.get_id().startswith('team_'):
        team = Team.query.get(int(current_user.get_id().split('_')[1]))
        if team and team.game_id == game.id:
            return redirect(url_for('player.quiz', game_code=game_code))

    return redirect(url_for('auth.player_login', game_code=game_code))


@bp.route('/questions/<game_code>')
@team_required
def next_questions(game_code):
    """
    Redirect to the next unanswered open round.

    Finds the first open round that the team hasn't submitted yet.
    If all done, redirects to waiting or game over page.
    """
    game = Game.query.filter_by(code=game_code.upper()).first_or_404()
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('auth.player_login', game_code=game_code))

    # If game is paused, show pause screen
    if game.pause_mode:
        return render_template('player/game_paused.html',
                              game=game,
                              team=team,
                              pause_mode=game.pause_mode,
                              active_nav='questions')

    # Get all rounds ordered - top-level rounds first (parent_id null), then by order
    rounds = Round.query.filter_by(game_id=game.id).order_by(
        Round.parent_id.isnot(None),  # False (0) for top-level, True (1) for children
        Round.order
    ).all()

    # Find submitted round IDs
    submitted_round_ids = set()
    for round_obj in rounds:
        if Answer.query.filter_by(team_id=team.id, round_id=round_obj.id).first():
            submitted_round_ids.add(round_obj.id)

    # Check for resubmit permissions
    resubmit_round_ids = set()
    permissions = ResubmitPermission.query.filter_by(team_id=team.id).all()
    for perm in permissions:
        resubmit_round_ids.add(perm.round_id)

    # Find next open round that hasn't been submitted (or has resubmit permission)
    for round_obj in rounds:
        # Skip parent rounds that have children (they don't have questions themselves)
        if round_obj.get_children():
            continue
        if round_obj.is_open:
            if round_obj.id not in submitted_round_ids:
                # Open and not submitted - go here
                return redirect(url_for('player.view_round', round_id=round_obj.id))
            elif round_obj.id in resubmit_round_ids:
                # Has resubmit permission - go here
                return redirect(url_for('player.view_round', round_id=round_obj.id))

    # No open unanswered rounds - check if game is over
    all_closed = all(not r.is_open for r in rounds)
    all_submitted = len(submitted_round_ids) >= len(rounds)

    if all_closed and all_submitted and len(rounds) > 0:
        return redirect(url_for('player.game_over', game_code=game.code))

    # Otherwise go to waiting page
    return redirect(url_for('player.waiting', game_code=game.code))


@bp.route('/quiz/<game_code>')
@team_required
def quiz(game_code):
    """
    Main quiz interface for players.

    Shows all rounds and their status.
    """
    game = Game.query.filter_by(code=game_code.upper()).first_or_404()
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('auth.player_login', game_code=game_code))

    # Get only top-level rounds for display
    rounds = Round.query.filter_by(game_id=game.id, parent_id=None).order_by(Round.order).all()

    # Get all rounds (including nested) for checking submissions and game-over status
    all_rounds = Round.query.filter_by(game_id=game.id).all()

    # Check which rounds team has submitted (including nested rounds)
    submitted_rounds = set()
    for round_obj in all_rounds:
        if Answer.query.filter_by(team_id=team.id, round_id=round_obj.id).first():
            submitted_rounds.add(round_obj.id)

    # Check if game is over (all rounds closed and team has submitted all)
    if all_rounds:
        all_closed = all(not r.is_open for r in all_rounds)
        all_submitted = len(submitted_rounds) >= len(all_rounds)
        if all_closed and all_submitted:
            return redirect(url_for('player.game_over', game_code=game.code))

    # Check which rounds have resubmit permission
    resubmit_rounds = set()
    permissions = ResubmitPermission.query.filter_by(team_id=team.id).all()
    for perm in permissions:
        resubmit_rounds.add(perm.round_id)

    # Calculate team score (full calculation: points + bonus - penalty + custom - tab_penalty)
    score_result = db.session.query(
        func.coalesce(func.sum(Answer.points), 0) +
        func.coalesce(func.sum(Answer.bonus_points), 0) -
        func.coalesce(func.sum(Answer.penalty_points), 0)
    ).filter(Answer.team_id == team.id).scalar() or 0

    # Add custom scores
    custom_scores = team.get_custom_scores()
    custom_total = sum(custom_scores.values()) if custom_scores else 0

    # Subtract tab penalty
    tab_penalty = team.tab_penalty_points

    team_score = int(score_result + custom_total - tab_penalty)

    return render_template('player/quiz.html',
                          game=game,
                          team=team,
                          rounds=rounds,
                          submitted_rounds=submitted_rounds,
                          resubmit_rounds=resubmit_rounds,
                          team_score=int(team_score),
                          pause_mode=game.pause_mode,
                          active_nav='rounds')


@bp.route('/round/<int:round_id>')
@team_required
def view_round(round_id):
    """
    View questions for a specific round.
    """
    round_obj = Round.query.get_or_404(round_id)
    game = round_obj.game
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('index'))

    # Check if game is paused - if so, show pause screen for answering new questions
    # But allow viewing previous answers (read_only mode)
    existing_answers = Answer.query.filter_by(team_id=team.id, round_id=round_obj.id).all()
    if game.pause_mode and not existing_answers:
        # Game is paused and no previous answers to view - show pause screen
        return render_template('player/game_paused.html',
                              game=game,
                              team=team,
                              pause_mode=game.pause_mode,
                              active_nav='questions')

    # If this round has sub-rounds, redirect to next available question
    children = round_obj.get_children()
    if children:
        return redirect(url_for('player.next_questions', game_code=game.code))

    # existing_answers already queried above for pause check

    # Check for resubmit permission
    can_resubmit = ResubmitPermission.query.filter_by(
        team_id=team.id,
        round_id=round_obj.id
    ).first() is not None

    # Determine if read-only mode (submitted without resubmit permission)
    read_only = bool(existing_answers) and not can_resubmit

    # If round is closed and no answers submitted, redirect
    if not round_obj.is_open and not existing_answers:
        flash('This round is closed.', 'warning')
        return redirect(url_for('player.next_questions', game_code=game.code))

    questions = round_obj.get_questions()

    # Build a dict of existing answers for pre-filling the form
    # Also build a dict of answer points (for showing correct/incorrect in read_only mode)
    existing_answers_dict = {}
    answer_points_dict = {}
    for answer in existing_answers:
        existing_answers_dict[answer.question_id] = answer.answer_text
        answer_points_dict[answer.question_id] = answer.points or 0

    # Check if this is the final round (for game complete popup)
    # Count all rounds that need submissions (excluding parent rounds that only have children)
    all_rounds = Round.query.filter_by(game_id=game.id).all()
    answerable_rounds = [r for r in all_rounds if not r.get_children()]  # Only leaf rounds
    submitted_round_ids = set()
    for r in answerable_rounds:
        if r.id != round_obj.id and Answer.query.filter_by(team_id=team.id, round_id=r.id).first():
            submitted_round_ids.add(r.id)

    # This round will be final if: all other answerable rounds are submitted
    # (and this is the last one being submitted now)
    is_potential_final = len(submitted_round_ids) == len(answerable_rounds) - 1
    total_answerable_rounds = len(answerable_rounds)
    submitted_count = len(submitted_round_ids)

    return render_template('player/round.html',
                          game=game,
                          round=round_obj,
                          team=team,
                          questions=questions,
                          existing_answers=existing_answers_dict,
                          answer_points=answer_points_dict,
                          is_resubmit=can_resubmit,
                          read_only=read_only,
                          is_potential_final=is_potential_final,
                          total_answerable_rounds=total_answerable_rounds,
                          submitted_count=submitted_count,
                          active_nav='questions')


@bp.route('/submit_round/<int:round_id>', methods=['POST'])
@team_required
def submit_round(round_id):
    """
    Submit answers for a round.
    """
    round_obj = Round.query.get_or_404(round_id)
    game = round_obj.game
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('index'))

    # Check if round is open
    if not round_obj.is_open:
        flash('This round is closed. Your answers were not submitted.', 'danger')
        return redirect(url_for('player.quiz', game_code=game.code))

    # Check if already submitted and if resubmit is allowed
    existing_answers = Answer.query.filter_by(team_id=team.id, round_id=round_obj.id).all()
    resubmit_permission = ResubmitPermission.query.filter_by(
        team_id=team.id,
        round_id=round_obj.id
    ).first()

    if existing_answers and not resubmit_permission:
        flash('You have already submitted answers for this round.', 'danger')
        return redirect(url_for('player.quiz', game_code=game.code))

    # Build lookup of existing answers
    existing_by_question = {a.question_id: a for a in existing_answers}

    # Process answers
    questions = round_obj.get_questions()
    all_answers = {}
    import json

    for q in questions:
        q_id = q.get('id', '')
        q_type = q.get('type', 'text')

        # Handle betting questions specially
        if q_type == 'betting':
            bet_amount = request.form.get(f'bet_amount_{q_id}', '1')
            bet_choice = request.form.get(f'bet_choice_{q_id}', '')

            # Validate bet amount against max
            betting_config = q.get('betting', {})
            max_bet = betting_config.get('max_bet', 3)
            try:
                bet_amount = int(bet_amount)
                bet_amount = max(1, min(bet_amount, max_bet))  # Clamp to valid range
            except (ValueError, TypeError):
                bet_amount = 1

            # Store as JSON
            answer_text = json.dumps({
                'bet_amount': bet_amount,
                'choice': bet_choice
            })

            # Points for betting = negative bet amount (deducted until results are set)
            points = -bet_amount

        # Handle ordering questions specially
        elif q_type == 'ordering':
            ordering_config = q.get('ordering', {})
            correct_items = ordering_config.get('items', [])
            points_exact = ordering_config.get('points_exact', 2)
            points_adjacent = ordering_config.get('points_adjacent', 1)

            # Collect player's ordering from form fields
            player_order = []
            for i in range(len(correct_items)):
                item = request.form.get(f'ordering_{q_id}_{i}', '')
                player_order.append(item)

            # Store as JSON array
            answer_text = json.dumps(player_order)

            # Calculate points based on position accuracy
            points = 0
            for player_pos, player_item in enumerate(player_order):
                if player_item and player_item in correct_items:
                    correct_pos = correct_items.index(player_item)
                    distance = abs(player_pos - correct_pos)
                    if distance == 0:
                        points += points_exact  # Exact position
                    elif distance == 1:
                        points += points_adjacent  # Off by one
                    # Off by more = 0 points

        # Handle estimate questions specially
        elif q_type == 'estimate':
            estimate_config = q.get('estimate', {})
            correct_answer = estimate_config.get('correct_answer')
            points_exact = estimate_config.get('points_exact', 4)
            points_10 = estimate_config.get('points_10', 3)
            points_20 = estimate_config.get('points_20', 2)
            points_30 = estimate_config.get('points_30', 1)

            answer_text = request.form.get(f'answer_{q_id}', '').strip()

            # Calculate points based on percentage distance from correct answer
            points = 0
            if answer_text and correct_answer is not None:
                try:
                    player_answer = float(answer_text)
                    correct_val = float(correct_answer)

                    if correct_val == 0:
                        # Special case: if correct answer is 0, exact match only
                        if player_answer == 0:
                            points = points_exact
                    else:
                        # Calculate percentage difference
                        pct_diff = abs(player_answer - correct_val) / abs(correct_val)

                        if pct_diff == 0:
                            points = points_exact
                        elif pct_diff <= 0.10:
                            points = points_10
                        elif pct_diff <= 0.20:
                            points = points_20
                        elif pct_diff <= 0.30:
                            points = points_30
                        # else: 0 points
                except (ValueError, TypeError):
                    points = 0

        else:
            answer_text = request.form.get(f'answer_{q_id}', '').strip()
            all_answers[q_id] = answer_text

            # Calculate points
            points = calculate_points_for_answer(q, answer_text, all_answers)

        # Update existing or create new answer
        if q_id in existing_by_question:
            # Update existing answer
            answer = existing_by_question[q_id]
            answer.answer_text = answer_text
            answer.points = points
            answer.submitted_at = db.func.now()
        else:
            # Create new answer record
            answer = Answer(
                team_id=team.id,
                round_id=round_obj.id,
                question_id=q_id,
                answer_text=answer_text,
                points=points
            )
            db.session.add(answer)

    try:
        # Remove resubmit permission if it exists
        if resubmit_permission:
            db.session.delete(resubmit_permission)

        db.session.commit()

        # Emit Socket.IO events for real-time update (if available)
        try:
            from app import socketio

            total_teams = Team.query.filter_by(game_id=game.id).count()
            submitted_teams = db.session.query(Answer.team_id).filter_by(round_id=round_obj.id).distinct().count()

            socketio.emit('submission_update', {
                'round_id': round_obj.id,
                'submissions': submitted_teams,
                'total_teams': total_teams
            }, room=f'game_{game.id}')

        except Exception:
            pass  # Socket.IO not available or error

    except Exception as e:
        db.session.rollback()
        flash('Error submitting answers. Please try again.', 'danger')
        return redirect(url_for('player.quiz', game_code=game.code))

    # Check if this is a sub-round with more siblings to complete
    if round_obj.parent_id:
        # Find the next sibling sub-round (same parent, higher order, open)
        next_sibling = Round.query.filter(
            Round.parent_id == round_obj.parent_id,
            Round.order > round_obj.order,
            Round.is_open == True
        ).order_by(Round.order).first()

        if next_sibling:
            # Check if team hasn't submitted this one yet
            already_submitted = Answer.query.filter_by(
                team_id=team.id,
                round_id=next_sibling.id
            ).first()

            if not already_submitted:
                # Go directly to next sub-round
                flash(f'Answers recorded! Moving to next section...', 'success')
                return redirect(url_for('player.view_round', round_id=next_sibling.id))

    # Otherwise, redirect back to rounds menu
    flash(f'Your answers for "{round_obj.name}" have been recorded!', 'success')
    return redirect(url_for('player.quiz', game_code=game.code))


@bp.route('/team/<game_code>')
@team_required
def team_details(game_code):
    """
    Team details page showing team stats and info.
    """
    game = Game.query.filter_by(code=game_code.upper()).first_or_404()
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('auth.player_login', game_code=game_code))

    # Calculate stats
    total_points = db.session.query(func.sum(Answer.points)).filter_by(team_id=team.id).scalar() or 0

    # Only count top-level rounds for display
    top_level_rounds = Round.query.filter_by(game_id=game.id, parent_id=None).all()
    total_rounds = len(top_level_rounds)

    # Count completed top-level rounds
    submitted_round_ids = set(
        r[0] for r in db.session.query(Answer.round_id).filter_by(team_id=team.id).distinct().all()
    )

    rounds_completed = 0
    for parent in top_level_rounds:
        if parent.id in submitted_round_ids:
            rounds_completed += 1
        else:
            children = Round.query.filter_by(parent_id=parent.id).all()
            if children and all(c.id in submitted_round_ids for c in children):
                rounds_completed += 1

    # Calculate position
    team_scores = db.session.query(
        Answer.team_id,
        func.sum(Answer.points).label('total')
    ).filter(
        Answer.team_id.in_([t.id for t in Team.query.filter_by(game_id=game.id).all()])
    ).group_by(Answer.team_id).order_by(func.sum(Answer.points).desc()).all()

    position = 1
    for idx, (tid, score) in enumerate(team_scores, 1):
        if tid == team.id:
            position = idx
            break

    # Position suffix
    if position == 1:
        position_suffix = 'st'
    elif position == 2:
        position_suffix = 'nd'
    elif position == 3:
        position_suffix = 'rd'
    else:
        position_suffix = 'th'

    return render_template('player/team_details.html',
                          game=game,
                          team=team,
                          total_points=int(total_points),
                          total_rounds=total_rounds,
                          rounds_completed=rounds_completed,
                          position=position,
                          position_suffix=position_suffix,
                          active_nav='team')


@bp.route('/instructions/<game_code>')
@team_required
def instructions(game_code):
    """
    Instructions page with tutorial on how to use the app.
    """
    game = Game.query.filter_by(code=game_code.upper()).first_or_404()
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('auth.player_login', game_code=game_code))

    # Check if this is a new team (show ready button)
    show_ready_button = request.args.get('new', False)

    return render_template('player/instructions.html',
                          game=game,
                          team=team,
                          show_ready_button=show_ready_button,
                          active_nav='help')


@bp.route('/ready/<game_code>')
@team_required
def ready(game_code):
    """
    Ready page shown after signup and instructions.
    """
    game = Game.query.filter_by(code=game_code.upper()).first_or_404()
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('auth.player_login', game_code=game_code))

    return render_template('player/ready.html',
                          game=game,
                          team=team,
                          show_nav=False)


@bp.route('/waiting/<game_code>')
@team_required
def waiting(game_code):
    """
    Waiting page shown after submitting answers for a round.
    """
    game = Game.query.filter_by(code=game_code.upper()).first_or_404()
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('auth.player_login', game_code=game_code))

    # Get round info
    round_id = request.args.get('round_id', type=int)
    round_obj = Round.query.get(round_id) if round_id else None
    last_round_name = round_obj.name if round_obj else "the round"

    # Calculate progress - only count top-level rounds for display
    top_level_rounds = Round.query.filter_by(game_id=game.id, parent_id=None).all()
    total_rounds = len(top_level_rounds)

    # Count completed top-level rounds (a parent is complete if team has submitted it or all its children)
    submitted_round_ids = set(
        r[0] for r in db.session.query(Answer.round_id).filter_by(team_id=team.id).distinct().all()
    )

    rounds_completed = 0
    for parent in top_level_rounds:
        # Check if parent itself was submitted
        if parent.id in submitted_round_ids:
            rounds_completed += 1
        else:
            # Check if all children were submitted (if it has children)
            children = Round.query.filter_by(parent_id=parent.id).all()
            if children and all(c.id in submitted_round_ids for c in children):
                rounds_completed += 1

    # Check if game is over (all rounds closed and team has submitted all)
    all_rounds = Round.query.filter_by(game_id=game.id).all()
    all_closed = all(not r.is_open for r in all_rounds)
    all_submitted_ids = set(r[0] for r in db.session.query(Answer.round_id).filter_by(team_id=team.id).distinct().all())
    all_submitted = len(all_submitted_ids) >= len(all_rounds)

    if all_closed and all_submitted and len(all_rounds) > 0:
        return redirect(url_for('player.game_over', game_code=game.code))

    return render_template('player/waiting.html',
                          game=game,
                          team=team,
                          last_round_name=last_round_name,
                          total_rounds=total_rounds,
                          rounds_completed=rounds_completed,
                          active_nav=None)


@bp.route('/game-over/<game_code>')
@team_required
def game_over(game_code):
    """
    Game over page shown when all rounds are closed and submitted.
    """
    game = Game.query.filter_by(code=game_code.upper()).first_or_404()
    team = Team.query.get(int(current_user.get_id().split('_')[1]))

    # Verify team belongs to this game
    if team.game_id != game.id:
        flash('You are not registered for this game.', 'danger')
        return redirect(url_for('auth.player_login', game_code=game_code))

    return render_template('player/game_over.html',
                          game=game,
                          team=team,
                          active_nav=None)

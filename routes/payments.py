"""
Payment routes for Quiz App.

Handles pricing page, Stripe Checkout, webhooks, and success/cancel pages.
"""
import os
import json
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

import stripe

from models import db, Admin, Subscription, PaymentEvent
from email_service import (
    send_event_purchase_confirmation,
    send_pro_subscription_started,
    send_pro_subscription_renewed,
    send_pro_subscription_cancelled,
    send_payment_failed,
    send_admin_sale_notification,
    send_admin_cancellation_notification,
    send_admin_payment_failed_notification,
)

bp = Blueprint('payments', __name__)


def _load_stripe_prices():
    """Load price map from stripe_prices.json."""
    prices_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'stripe_prices.json')
    try:
        with open(prices_path) as f:
            return json.load(f)
    except FileNotFoundError:
        print('[Payments] stripe_prices.json not found - run scripts/create_stripe_products.py first')
        return {}


def _get_or_create_subscription(admin_id):
    """Get or create a Subscription record for an admin."""
    sub = Subscription.query.filter_by(admin_id=admin_id).first()
    if not sub:
        sub = Subscription(admin_id=admin_id, plan_type='free', max_teams=5)
        db.session.add(sub)
        db.session.commit()
    return sub


def admin_required(f):
    """Require admin authentication."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.get_id().startswith('admin_'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated


# ===== Pricing page =====

@bp.route('/pricing')
def pricing():
    """Public pricing page."""
    prices = _load_stripe_prices()

    # Build event tiers
    event_tiers = []
    for teams in [5, 10, 20, 50, 100]:
        key = f'event_{teams}'
        if key in prices:
            event_tiers.append({
                'teams': teams,
                'price_monthly': prices[key]['amount'],
                'price_id': prices[key]['price_id'],
            })

    # Build pro tiers
    pro_tiers = []
    for games in [1, 4, 8, 16, 32]:
        tier = {'games': games, 'team_options': []}
        for teams in [5, 10, 20, 50, 100]:
            monthly_key = f'pro_monthly_{games}g_{teams}t'
            yearly_key = f'pro_yearly_{games}g_{teams}t'
            if monthly_key in prices:
                tier['team_options'].append({
                    'teams': teams,
                    'monthly_price': prices[monthly_key]['amount'],
                    'monthly_price_id': prices[monthly_key]['price_id'],
                    'yearly_price': prices.get(yearly_key, {}).get('amount', 0),
                    'yearly_price_id': prices.get(yearly_key, {}).get('price_id', ''),
                })
        if tier['team_options']:
            pro_tiers.append(tier)

    # Current subscription info for logged-in admins
    current_plan = None
    if current_user.is_authenticated and current_user.get_id().startswith('admin_'):
        admin_id = int(current_user.get_id().split('_')[1])
        sub = _get_or_create_subscription(admin_id)
        current_plan = sub.plan_display

    return render_template('pricing.html',
                           event_tiers=event_tiers,
                           pro_tiers=pro_tiers,
                           current_plan=current_plan,
                           stripe_pk=current_app.config.get('STRIPE_PUBLISHABLE_KEY', ''))


# ===== Checkout =====

@bp.route('/checkout', methods=['POST'])
@admin_required
def create_checkout():
    """Create a Stripe Checkout session."""
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    price_id = request.form.get('price_id')
    plan_type = request.form.get('plan_type', '')  # 'event' or 'pro_monthly' or 'pro_yearly'
    max_teams = request.form.get('max_teams', '5')
    games_per_month = request.form.get('games_per_month', '0')

    if not price_id:
        flash('Invalid plan selected.', 'danger')
        return redirect(url_for('payments.pricing'))

    admin_id = int(current_user.get_id().split('_')[1])
    admin = Admin.query.get(admin_id)
    sub = _get_or_create_subscription(admin_id)

    # Get or create Stripe customer
    if not sub.stripe_customer_id:
        customer = stripe.Customer.create(
            email=admin.email or '',
            metadata={'admin_id': str(admin_id), 'username': admin.username},
        )
        sub.stripe_customer_id = customer.id
        db.session.commit()

    # Determine mode
    mode = 'subscription' if plan_type.startswith('pro_') else 'payment'

    session_params = {
        'customer': sub.stripe_customer_id,
        'payment_method_types': ['card'],
        'line_items': [{'price': price_id, 'quantity': 1}],
        'mode': mode,
        'success_url': request.host_url.rstrip('/') + url_for('payments.checkout_success') + '?session_id={CHECKOUT_SESSION_ID}',
        'cancel_url': request.host_url.rstrip('/') + url_for('payments.checkout_cancel'),
        'metadata': {
            'admin_id': str(admin_id),
            'plan_type': plan_type,
            'max_teams': max_teams,
            'games_per_month': games_per_month,
        },
    }

    # For subscriptions, also attach metadata to the subscription
    if mode == 'subscription':
        session_params['subscription_data'] = {
            'metadata': {
                'admin_id': str(admin_id),
                'plan_type': plan_type,
                'max_teams': max_teams,
                'games_per_month': games_per_month,
            },
        }

    checkout_session = stripe.checkout.Session.create(**session_params)
    print(f'[Payments] Checkout session created: {checkout_session.id} for admin {admin_id}, plan={plan_type}')

    return redirect(checkout_session.url, code=303)


@bp.route('/checkout/success')
@admin_required
def checkout_success():
    """Post-checkout success page."""
    flash('Payment successful! Your plan has been updated.', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/checkout/cancel')
def checkout_cancel():
    """Post-checkout cancel page."""
    flash('Checkout cancelled.', 'info')
    return redirect(url_for('payments.pricing'))


# ===== Stripe Webhooks =====

@bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events."""
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET', '')

    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            # Dev mode - parse without signature verification
            event = json.loads(payload)
            print('[Payments] WARNING: No webhook secret set, skipping signature verification')
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        print(f'[Payments] Webhook signature verification failed: {e}')
        return jsonify({'error': 'Invalid signature'}), 400

    event_type = event.get('type', '')
    print(f'[Payments] Webhook received: {event_type}')

    # Check for duplicate events
    stripe_event_id = event.get('id', '')
    if PaymentEvent.query.filter_by(stripe_event_id=stripe_event_id).first():
        print(f'[Payments] Duplicate event, skipping: {stripe_event_id}')
        return jsonify({'status': 'duplicate'}), 200

    try:
        if event_type == 'checkout.session.completed':
            _handle_checkout_completed(event)
        elif event_type == 'invoice.paid':
            _handle_invoice_paid(event)
        elif event_type == 'customer.subscription.deleted':
            _handle_subscription_deleted(event)
        elif event_type == 'invoice.payment_failed':
            _handle_payment_failed(event)
        else:
            print(f'[Payments] Unhandled event type: {event_type}')
    except Exception as e:
        print(f'[Payments] Error handling {event_type}: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    return jsonify({'status': 'ok'}), 200


def _handle_checkout_completed(event):
    """Handle checkout.session.completed - provision access."""
    session = event['data']['object']
    metadata = session.get('metadata', {})
    admin_id = metadata.get('admin_id')
    plan_type = metadata.get('plan_type', '')
    max_teams = int(metadata.get('max_teams', 5))
    games_per_month = int(metadata.get('games_per_month', 0))
    customer_id = session.get('customer')

    if not admin_id:
        print('[Payments] No admin_id in checkout metadata, skipping')
        return

    admin_id = int(admin_id)
    admin = Admin.query.get(admin_id)
    if not admin:
        print(f'[Payments] Admin {admin_id} not found')
        return

    sub = _get_or_create_subscription(admin_id)
    sub.stripe_customer_id = customer_id

    amount = session.get('amount_total', 0)
    amount_display = f'£{amount / 100:.2f}'

    if plan_type == 'event':
        # One-off event purchase - add a game credit
        sub.event_games_remaining = (sub.event_games_remaining or 0) + 1
        sub.max_teams = max(sub.max_teams or 5, max_teams)
        if sub.plan_type == 'free':
            sub.plan_type = 'event'

        db.session.commit()

        # Customer email
        if admin.email:
            send_event_purchase_confirmation(admin.email, max_teams, amount_display)

        # Admin notification
        send_admin_sale_notification(
            admin.email or admin.username,
            f'Event ({max_teams} teams)',
            amount_display,
        )

    elif plan_type.startswith('pro_'):
        # Pro subscription
        sub.plan_type = plan_type
        sub.games_per_month = games_per_month
        sub.max_teams = max_teams
        sub.is_active = True
        sub.games_created_this_period = 0
        sub.stripe_subscription_id = session.get('subscription')
        sub.stripe_price_id = metadata.get('price_id', '')
        sub.current_period_start = datetime.utcnow()

        db.session.commit()

        billing_cycle = 'monthly' if plan_type == 'pro_monthly' else 'yearly'

        # Customer email
        if admin.email:
            send_pro_subscription_started(admin.email, games_per_month, max_teams, amount_display, billing_cycle)

        # Admin notification
        send_admin_sale_notification(
            admin.email or admin.username,
            f'Pro {billing_cycle} ({games_per_month}/month, {max_teams} teams)',
            amount_display,
        )

    # Log the event
    pe = PaymentEvent(
        admin_id=admin_id,
        event_type='checkout_completed',
        stripe_event_id=event['id'],
        stripe_customer_id=customer_id,
        amount=amount,
        plan_type=plan_type,
        metadata_json=json.dumps(metadata),
    )
    db.session.add(pe)
    db.session.commit()

    print(f'[Payments] Checkout completed: admin={admin_id}, plan={plan_type}, amount={amount_display}')


def _handle_invoice_paid(event):
    """Handle invoice.paid - renewal for subscriptions."""
    invoice = event['data']['object']
    subscription_id = invoice.get('subscription')
    customer_id = invoice.get('customer')

    if not subscription_id:
        return  # Not a subscription invoice

    # Skip the first invoice (handled by checkout.session.completed)
    if invoice.get('billing_reason') == 'subscription_create':
        print('[Payments] Skipping initial subscription invoice (handled by checkout)')
        return

    sub = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
    if not sub:
        print(f'[Payments] No subscription found for {subscription_id}')
        return

    # Reset period counter
    sub.games_created_this_period = 0
    sub.current_period_start = datetime.utcnow()

    amount = invoice.get('amount_paid', 0)
    amount_display = f'£{amount / 100:.2f}'

    # Get next billing date
    next_date = ''
    try:
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        next_ts = stripe_sub.get('current_period_end')
        if next_ts:
            next_date = datetime.fromtimestamp(next_ts).strftime('%d %b %Y')
    except Exception as e:
        print(f'[Payments] Could not fetch next billing date: {e}')

    db.session.commit()

    admin = Admin.query.get(sub.admin_id)
    if admin and admin.email:
        send_pro_subscription_renewed(admin.email, sub.games_per_month, sub.max_teams, amount_display, next_date)

    # Log
    pe = PaymentEvent(
        admin_id=sub.admin_id,
        event_type='invoice_paid',
        stripe_event_id=event['id'],
        stripe_customer_id=customer_id,
        amount=amount,
        plan_type=sub.plan_type,
    )
    db.session.add(pe)
    db.session.commit()

    print(f'[Payments] Invoice paid (renewal): admin={sub.admin_id}, amount={amount_display}')


def _handle_subscription_deleted(event):
    """Handle customer.subscription.deleted - cancel access."""
    subscription = event['data']['object']
    subscription_id = subscription.get('id')

    sub = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
    if not sub:
        print(f'[Payments] No subscription found for {subscription_id}')
        return

    plan_description = sub.plan_display
    sub.is_active = False
    sub.cancelled_at = datetime.utcnow()
    sub.plan_type = 'free'
    sub.games_per_month = 0
    sub.max_teams = 5
    sub.stripe_subscription_id = None

    db.session.commit()

    admin = Admin.query.get(sub.admin_id)
    access_end = datetime.fromtimestamp(subscription.get('current_period_end', 0)).strftime('%d %b %Y')

    if admin and admin.email:
        send_pro_subscription_cancelled(admin.email, access_end)

    send_admin_cancellation_notification(admin.email or admin.username if admin else 'unknown', plan_description)

    # Log
    pe = PaymentEvent(
        admin_id=sub.admin_id,
        event_type='subscription_cancelled',
        stripe_event_id=event['id'],
        stripe_customer_id=subscription.get('customer'),
        plan_type='cancelled',
    )
    db.session.add(pe)
    db.session.commit()

    print(f'[Payments] Subscription cancelled: admin={sub.admin_id}')


def _handle_payment_failed(event):
    """Handle invoice.payment_failed - notify customer and admin."""
    invoice = event['data']['object']
    subscription_id = invoice.get('subscription')
    customer_id = invoice.get('customer')

    sub = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first() if subscription_id else None

    customer_email = invoice.get('customer_email', '')
    plan_description = sub.plan_display if sub else 'Unknown'

    # Get failure reason
    failure_reason = None
    charge_id = invoice.get('charge')
    if charge_id:
        try:
            stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
            charge = stripe.Charge.retrieve(charge_id)
            failure_reason = charge.get('failure_message')
        except Exception:
            pass

    if customer_email:
        send_payment_failed(customer_email)

    send_admin_payment_failed_notification(customer_email or 'unknown', plan_description, failure_reason)

    # Log
    pe = PaymentEvent(
        admin_id=sub.admin_id if sub else None,
        event_type='payment_failed',
        stripe_event_id=event['id'],
        stripe_customer_id=customer_id,
        amount=invoice.get('amount_due', 0),
        plan_type=sub.plan_type if sub else None,
    )
    db.session.add(pe)
    db.session.commit()

    print(f'[Payments] Payment failed: customer={customer_email}')

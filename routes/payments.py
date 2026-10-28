"""
Payment routes for Quiz App.

Handles pricing page, checkout via centralised Payments service,
callbacks, and success/cancel pages.
"""
import os
import json
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify

from lozzalingo.clients.payments_client import PaymentsClient

from models import db, Admin, Subscription, PaymentEvent

try:
    from lozzalingo.core import db_log
except ImportError:
    def db_log(*args, **kwargs):
        pass

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
payments = PaymentsClient()


def _load_stripe_prices():
    """Load price map from stripe_prices.json."""
    prices_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'stripe_prices.json')
    try:
        with open(prices_path) as f:
            return json.load(f)
    except FileNotFoundError:
        print('[Payments] stripe_prices.json not found - run scripts/create_stripe_products.py first')
        return {}


def _find_price_info(price_id):
    """Find price details by Stripe price ID (reverse lookup)."""
    prices = _load_stripe_prices()
    for key, data in prices.items():
        if data.get('price_id') == price_id:
            return data
    return None


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
    def decorated(*args, **kwargs):
        from flask_login import login_required, current_user
        # login_required is applied via the route decorator
        if not current_user.is_authenticated:
            return redirect(url_for('auth.admin_login'))
        if not current_user.get_id().startswith('admin_'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated


# ===== Pricing page =====

@bp.route('/pricing')
def pricing():
    print(f'[Payments] pricing handler called')
    """Public pricing page."""
    from flask_login import current_user

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
                           stripe_pk='')


# ===== Checkout =====

@bp.route('/checkout', methods=['POST'])
@admin_required
def create_checkout():
    """Create a checkout session via the centralised payments service."""
    from flask_login import current_user

    price_id = request.form.get('price_id')
    plan_type = request.form.get('plan_type', '')
    max_teams = request.form.get('max_teams', '5')
    games_per_month = request.form.get('games_per_month', '0')

    if not price_id:
        flash('Invalid plan selected.', 'danger')
        return redirect(url_for('payments.pricing'))

    admin_id = int(current_user.get_id().split('_')[1])
    admin = Admin.query.get(admin_id)

    metadata = {
        'admin_id': str(admin_id),
        'plan_type': plan_type,
        'max_teams': max_teams,
        'games_per_month': games_per_month,
    }

    success_url = request.host_url.rstrip('/') + url_for('payments.checkout_success') + '?session_id={CHECKOUT_SESSION_ID}'
    cancel_url = request.host_url.rstrip('/') + url_for('payments.checkout_cancel')

    if plan_type == 'event':
        # One-time event purchase - look up amount from prices
        price_info = _find_price_info(price_id)
        if not price_info:
            flash('Invalid price selected.', 'danger')
            return redirect(url_for('payments.pricing'))

        result = payments.create_checkout(
            line_items=[{
                'name': f'Quiz Event - {max_teams} Teams',
                'price_pence': price_info['amount'],
                'quantity': 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=admin.email or '',
            metadata=metadata,
        )

    elif plan_type.startswith('pro_'):
        # Subscription checkout - pass the Stripe price ID
        result = payments.create_subscription_checkout(
            line_items=[{'price_id': price_id, 'quantity': 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=admin.email or '',
            metadata=metadata,
        )

    else:
        flash('Invalid plan type.', 'danger')
        return redirect(url_for('payments.pricing'))

    if not result:
        db_log('error', 'payments', 'Failed to create checkout session', {
            'admin_id': admin_id, 'plan_type': plan_type,
        })
        flash('Could not create checkout session. Please try again.', 'danger')
        return redirect(url_for('payments.pricing'))

    checkout_url = result.get('checkout_url')
    print(f'[Payments] Checkout session created: {result.get("session_id")} for admin {admin_id}, plan={plan_type}')

    return redirect(checkout_url, code=303)


@bp.route('/checkout/success')
@admin_required
def checkout_success():
    print(f'[Payments] checkout_success handler called')
    """Post-checkout success page."""
    flash('Payment successful! Your plan has been updated.', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/checkout/cancel')
def checkout_cancel():
    print(f'[Payments] checkout_cancel handler called')
    """Post-checkout cancel page."""
    flash('Checkout cancelled.', 'info')
    return redirect(url_for('payments.pricing'))


# ===== Payment Callbacks =====

@bp.route('/payments/callback', methods=['POST'])
def payment_callback():
    """Handle callbacks from the centralised payments service."""
    data = payments.verify_callback(request)
    if data is None:
        # Fall back to raw JSON for dev/testing without signature
        data = request.get_json(silent=True)
        if data is None:
            db_log('warning', 'payments', 'Rejected callback with invalid payload')
            return jsonify({'error': 'Invalid payload'}), 400

    event_type = data.get('event_type', '')
    print(f'[Payments] Callback received: {event_type}')

    # Idempotency check
    event_key = data.get('session_id') or data.get('invoice_id') or data.get('subscription_id', '')
    dedup_id = f'{event_type}_{event_key}'
    if PaymentEvent.query.filter_by(stripe_event_id=dedup_id).first():
        print(f'[Payments] Duplicate callback, skipping: {dedup_id}')
        return jsonify({'status': 'duplicate'}), 200

    try:
        if event_type == 'checkout.session.completed':
            _handle_checkout_completed(data)
        elif event_type == 'invoice.paid':
            _handle_invoice_paid(data)
        elif event_type == 'customer.subscription.deleted':
            _handle_subscription_deleted(data)
        elif event_type == 'invoice.payment_failed':
            _handle_payment_failed(data)
        else:
            print(f'[Payments] Unhandled event type: {event_type}')
    except Exception as e:
        db_log('critical', 'payments', f'Callback handler error for {event_type}: {e}', {
            'event_type': event_type,
            'event_key': event_key,
        })
        print(f'[Payments] Error handling {event_type}: {e}')
        import traceback
        traceback.print_exc()
        # Return 200 to prevent retries for application errors
        return jsonify({'received': True, 'error': 'Handler failed'}), 200

    return jsonify({'received': True}), 200


def _handle_checkout_completed(data):
    """Handle checkout.session.completed - provision access."""
    metadata = data.get('metadata', {})
    admin_id = metadata.get('admin_id')
    plan_type = metadata.get('plan_type', '')
    max_teams = int(metadata.get('max_teams', 5))
    games_per_month = int(metadata.get('games_per_month', 0))
    customer_id = data.get('customer_id', '')

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

    amount = data.get('amount_total', 0)
    amount_display = f'\u00a3{amount / 100:.2f}'

    if plan_type == 'event':
        # One-off event purchase - add a game credit
        sub.event_games_remaining = (sub.event_games_remaining or 0) + 1
        sub.max_teams = max(sub.max_teams or 5, max_teams)
        if sub.plan_type == 'free':
            sub.plan_type = 'event'

        db.session.commit()

        if admin.email:
            send_event_purchase_confirmation(admin.email, max_teams, amount_display)

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
        sub.stripe_subscription_id = data.get('subscription_id')
        sub.stripe_price_id = metadata.get('price_id', '')
        sub.current_period_start = datetime.utcnow()

        db.session.commit()

        billing_cycle = 'monthly' if plan_type == 'pro_monthly' else 'yearly'

        if admin.email:
            send_pro_subscription_started(admin.email, games_per_month, max_teams, amount_display, billing_cycle)

        send_admin_sale_notification(
            admin.email or admin.username,
            f'Pro {billing_cycle} ({games_per_month}/month, {max_teams} teams)',
            amount_display,
        )

    # Log the event
    session_id = data.get('session_id', '')
    pe = PaymentEvent(
        admin_id=admin_id,
        event_type='checkout_completed',
        stripe_event_id=f'checkout.session.completed_{session_id}',
        stripe_customer_id=customer_id,
        amount=amount,
        plan_type=plan_type,
        metadata_json=json.dumps(metadata),
    )
    db.session.add(pe)
    db.session.commit()

    # Log conversion for analytics attribution
    try:
        from lozzalingo.clients.analytics_client import AnalyticsClient
        _analytics = AnalyticsClient()
        _analytics.log_conversion(
            site_id='quiz-app',
            conversion_type='subscription' if plan_type.startswith('pro_') else 'purchase',
            order_id=session_id,
            order_value=amount,
            customer_email=admin.email if admin else None,
            metadata={'plan_type': plan_type, 'max_teams': max_teams},
        )
    except Exception:
        pass  # Analytics not critical to payment flow

    db_log('info', 'payments', f'Checkout completed: admin={admin_id}, plan={plan_type}, amount={amount_display}', {
        'admin_id': admin_id, 'plan_type': plan_type, 'amount': amount, 'max_teams': max_teams,
    })
    print(f'[Payments] Checkout completed: admin={admin_id}, plan={plan_type}, amount={amount_display}')


def _handle_invoice_paid(data):
    """Handle invoice.paid - renewal for subscriptions."""
    subscription_id = data.get('subscription_id')
    customer_id = data.get('customer_id')

    if not subscription_id:
        return  # Not a subscription invoice

    sub = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
    if not sub:
        print(f'[Payments] No subscription found for {subscription_id}')
        return

    # Skip the initial invoice (handled by checkout.session.completed)
    if sub.current_period_start and (datetime.utcnow() - sub.current_period_start).total_seconds() < 60:
        print('[Payments] Skipping initial subscription invoice (handled by checkout)')
        return

    # Reset period counter
    sub.games_created_this_period = 0
    sub.current_period_start = datetime.utcnow()

    amount = data.get('amount_paid', 0)
    amount_display = f'\u00a3{amount / 100:.2f}'

    # Get next billing date from payments service
    next_date = ''
    try:
        sub_details = payments.get_subscription(subscription_id)
        if sub_details:
            next_ts = sub_details.get('current_period_end')
            if next_ts:
                next_date = datetime.fromtimestamp(next_ts).strftime('%d %b %Y')
    except Exception as e:
        print(f'[Payments] Could not fetch next billing date: {e}')

    db.session.commit()

    admin = Admin.query.get(sub.admin_id)
    if admin and admin.email:
        send_pro_subscription_renewed(admin.email, sub.games_per_month, sub.max_teams, amount_display, next_date)

    # Log
    invoice_id = data.get('invoice_id', '')
    pe = PaymentEvent(
        admin_id=sub.admin_id,
        event_type='invoice_paid',
        stripe_event_id=f'invoice.paid_{invoice_id}',
        stripe_customer_id=customer_id,
        amount=amount,
        plan_type=sub.plan_type,
    )
    db.session.add(pe)
    db.session.commit()

    db_log('info', 'payments', f'Invoice paid (renewal): admin={sub.admin_id}, amount={amount_display}')
    print(f'[Payments] Invoice paid (renewal): admin={sub.admin_id}, amount={amount_display}')


def _handle_subscription_deleted(data):
    """Handle customer.subscription.deleted - cancel access."""
    subscription_id = data.get('subscription_id')

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
    access_end = datetime.utcnow().strftime('%d %b %Y')

    if admin and admin.email:
        send_pro_subscription_cancelled(admin.email, access_end)

    send_admin_cancellation_notification(admin.email or admin.username if admin else 'unknown', plan_description)

    # Log
    pe = PaymentEvent(
        admin_id=sub.admin_id,
        event_type='subscription_cancelled',
        stripe_event_id=f'customer.subscription.deleted_{subscription_id}',
        stripe_customer_id=data.get('customer_id', ''),
        plan_type='cancelled',
    )
    db.session.add(pe)
    db.session.commit()

    db_log('info', 'payments', f'Subscription cancelled: admin={sub.admin_id}', {'plan': plan_description})
    print(f'[Payments] Subscription cancelled: admin={sub.admin_id}')


def _handle_payment_failed(data):
    """Handle invoice.payment_failed - notify customer and admin."""
    subscription_id = data.get('subscription_id')
    customer_id = data.get('customer_id')
    customer_email = data.get('customer_email', '')

    sub = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first() if subscription_id else None
    plan_description = sub.plan_display if sub else 'Unknown'

    if customer_email:
        send_payment_failed(customer_email)

    send_admin_payment_failed_notification(customer_email or 'unknown', plan_description, None)

    # Log
    invoice_id = data.get('invoice_id', '')
    pe = PaymentEvent(
        admin_id=sub.admin_id if sub else None,
        event_type='payment_failed',
        stripe_event_id=f'invoice.payment_failed_{invoice_id}',
        stripe_customer_id=customer_id,
        amount=data.get('amount_due', 0),
        plan_type=sub.plan_type if sub else None,
    )
    db.session.add(pe)
    db.session.commit()

    db_log('warning', 'payments', f'Payment failed: customer={customer_email}', {
        'plan': plan_description,
    })
    print(f'[Payments] Payment failed: customer={customer_email}')

"""
Email Service - Quiz App (Fat Big Quiz)
Sends notification and transactional emails via the centralised Email Service.
"""
import os
from datetime import datetime

from lozzalingo.clients.email_client import EmailClient

try:
    from lozzalingo.core import db_log
except ImportError:
    def db_log(*args, **kwargs):
        pass


SITE_ID = 'fat-big-quiz'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'laurencedotcomputer@gmail.com')
BASE_URL = os.environ.get('BASE_URL', 'https://app.fatbigquiz.com')

SOURCE_LABELS = {
    'subscriber': 'Newsletter Signup',
    'quiz-pack': 'Quiz Pack (Coming Soon)',
    'quiz-database': 'Quiz Database (Coming Soon)',
    'quiz-app': 'Quiz App Beta Access',
}

# Centralised email client (reads EMAIL_SERVICE_URL and EMAIL_SERVICE_API_KEY from env)
_client = EmailClient()


def _send_email(to, subject, html, text=None):
    """Send an email via the centralised Email Service."""
    try:
        result = _client.send(
            to=to,
            subject=subject,
            html=html,
            site_id=SITE_ID,
            text=text,
        )
        if result and result.get('success'):
            print(f'[Email] Sent to {to} - subject="{subject}", id={result.get("email_id")}')
            return True
        else:
            error = result.get('error', 'Unknown error') if result else 'No response from email service'
            db_log('error', 'email_service', f'Failed to send email to {to}: {error}', {
                'subject': subject,
            })
            print(f'[Email] Failed to send to {to}: {error}')
            return False
    except Exception as e:
        db_log('error', 'email_service', f'Error sending email to {to}: {e}', {
            'subject': subject,
        })
        print(f'[Email] Error sending to {to}: {e}')
        return False


def _wrap_html(title, body):
    """Wrap email body in a consistent template."""
    return f"""
    <div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
        <div style="background:#7c3aed;padding:20px;border-radius:8px 8px 0 0;">
            <h2 style="color:#fff;margin:0;font-size:18px;">{title}</h2>
        </div>
        <div style="background:#fff;padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;">
            {body}
        </div>
        <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:16px;">Fat Big Quiz</p>
    </div>
    """


def _info_block(rows):
    """Build a summary block from a list of (label, value) tuples."""
    lines = []
    for label, value in rows:
        lines.append(f'<strong>{label}:</strong> {value}')
    return f'<div style="background:#f9fafb;border-radius:6px;border-left:4px solid #7c3aed;margin:16px 0;padding:12px 16px;line-height:1.8;">{"<br>".join(lines)}</div>'


# ===== List signup notification (existing) =====

def send_admin_list_notification(email, name=None, source='quiz-app'):
    """Send admin notification when someone joins a list."""
    source_label = SOURCE_LABELS.get(source, source)
    timestamp = datetime.now().strftime('%d %b %Y, %H:%M')

    rows = [('List', source_label)]
    if name:
        rows.append(('Name', name))
    rows.append(('Email', email))
    rows.append(('Time', timestamp))

    html = _wrap_html('New List Signup!', f'<h3 style="margin:0 0 8px;">Someone joined a list</h3>{_info_block(rows)}')
    text = f"New List Signup!\n\n" + "\n".join(f"{l}: {v}" for l, v in rows) + "\n\nFat Big Quiz"

    return _send_email(ADMIN_EMAIL, f'[FBQ] New signup: {source_label} - {email}', html, text)


# ===== Payment emails - Customer =====

def send_event_purchase_confirmation(customer_email, max_teams, amount_display):
    """Email 1: Confirm an event (one-off) purchase."""
    rows = [
        ('Plan', f'Event - up to {max_teams} teams'),
        ('Amount paid', amount_display),
    ]
    body = f"""
        <h3 style="margin:0 0 8px;">Thanks for your purchase!</h3>
        <p style="color:#5f6368;margin:0 0 16px;">You have unlocked a new game for up to {max_teams} teams. Head to your dashboard to create it.</p>
        {_info_block(rows)}
        <p style="text-align:center;margin-top:20px;">
            <a href="{BASE_URL}/admin/dashboard" style="display:inline-block;background:#7c3aed;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:600;">Create Your Game</a>
        </p>
    """
    html = _wrap_html('Purchase Confirmed!', body)
    text = f"Thanks for your purchase!\n\nPlan: Event - up to {max_teams} teams\nAmount: {amount_display}\n\nCreate your game: {BASE_URL}/admin/dashboard\n\nFat Big Quiz"

    return _send_email(customer_email, 'Fat Big Quiz - Purchase Confirmed!', html, text)


def send_pro_subscription_started(customer_email, games_per_month, max_teams, amount_display, billing_cycle):
    """Email 2: Welcome to Pro subscription."""
    rows = [
        ('Plan', f'Pro {billing_cycle.title()} - {games_per_month} quizzes/month'),
        ('Teams', f'Up to {max_teams} per game'),
        ('Amount', amount_display),
        ('Billing', billing_cycle.title()),
    ]
    body = f"""
        <h3 style="margin:0 0 8px;">Welcome to Pro!</h3>
        <p style="color:#5f6368;margin:0 0 16px;">You can now create up to {games_per_month} quizzes per month with up to {max_teams} teams each. Plus custom branding and CSV exports.</p>
        {_info_block(rows)}
        <p style="text-align:center;margin-top:20px;">
            <a href="{BASE_URL}/admin/dashboard" style="display:inline-block;background:#7c3aed;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:600;">Go to Dashboard</a>
        </p>
    """
    html = _wrap_html('Welcome to Pro!', body)
    text = f"Welcome to Pro!\n\nPlan: {games_per_month} quizzes/month, {max_teams} teams\nAmount: {amount_display}\nBilling: {billing_cycle}\n\nDashboard: {BASE_URL}/admin/dashboard\n\nFat Big Quiz"

    return _send_email(customer_email, 'Fat Big Quiz - Welcome to Pro!', html, text)


def send_pro_subscription_renewed(customer_email, games_per_month, max_teams, amount_display, next_billing_date):
    """Email 3: Pro subscription renewed."""
    rows = [
        ('Plan', f'Pro - {games_per_month} quizzes/month, {max_teams} teams'),
        ('Amount charged', amount_display),
        ('Next billing date', next_billing_date),
    ]
    body = f"""
        <h3 style="margin:0 0 8px;">Subscription renewed</h3>
        <p style="color:#5f6368;margin:0 0 16px;">Your Pro plan has renewed. Your quiz quota has been reset for this period.</p>
        {_info_block(rows)}
    """
    html = _wrap_html('Subscription Renewed', body)
    text = f"Subscription renewed\n\n" + "\n".join(f"{l}: {v}" for l, v in rows) + "\n\nFat Big Quiz"

    return _send_email(customer_email, 'Fat Big Quiz - Subscription Renewed', html, text)


def send_pro_subscription_cancelled(customer_email, access_end_date):
    """Email 4: Pro subscription cancelled."""
    body = f"""
        <h3 style="margin:0 0 8px;">Subscription cancelled</h3>
        <p style="color:#5f6368;margin:0 0 16px;">Your Pro plan has been cancelled. You can continue using Pro features until <strong>{access_end_date}</strong>.</p>
        <p style="color:#5f6368;margin:0 0 16px;">After that, your account will revert to the free tier. Your existing games and data will remain, but you will not be able to create new games beyond the free limit.</p>
        <p style="text-align:center;margin-top:20px;">
            <a href="{BASE_URL}/pricing" style="display:inline-block;background:#7c3aed;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:600;">Resubscribe</a>
        </p>
    """
    html = _wrap_html('Subscription Cancelled', body)
    text = f"Subscription cancelled\n\nYour Pro plan has been cancelled. Access until: {access_end_date}\n\nResubscribe: {BASE_URL}/pricing\n\nFat Big Quiz"

    return _send_email(customer_email, 'Fat Big Quiz - Subscription Cancelled', html, text)


def send_payment_failed(customer_email):
    """Email 5: Payment failed on renewal."""
    body = f"""
        <h3 style="margin:0 0 8px;">Payment failed</h3>
        <p style="color:#5f6368;margin:0 0 16px;">We could not process your latest payment. Please update your payment method to keep your Pro plan active.</p>
        <p style="color:#5f6368;margin:0 0 16px;">If we cannot collect payment, your plan will be cancelled automatically.</p>
        <p style="text-align:center;margin-top:20px;">
            <a href="{BASE_URL}/pricing" style="display:inline-block;background:#7c3aed;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:600;">Update Payment Method</a>
        </p>
    """
    html = _wrap_html('Payment Failed', body)
    text = f"Payment failed\n\nWe could not process your latest payment. Update your payment method at: {BASE_URL}/pricing\n\nFat Big Quiz"

    return _send_email(customer_email, 'Fat Big Quiz - Payment Failed', html, text)


# ===== Payment emails - Admin notifications =====

def send_admin_sale_notification(customer_email, plan_description, amount_display):
    """Email 6: Notify admin of a new sale."""
    timestamp = datetime.now().strftime('%d %b %Y, %H:%M')
    rows = [
        ('Customer', customer_email),
        ('Plan', plan_description),
        ('Amount', amount_display),
        ('Time', timestamp),
    ]
    html = _wrap_html('New Sale!', f'<h3 style="margin:0 0 8px;">Someone just paid</h3>{_info_block(rows)}')
    text = f"New Sale!\n\n" + "\n".join(f"{l}: {v}" for l, v in rows) + "\n\nFat Big Quiz"

    return _send_email(ADMIN_EMAIL, f'[FBQ] New sale: {plan_description} - {amount_display}', html, text)


def send_admin_cancellation_notification(customer_email, plan_description):
    """Email 7: Notify admin of a subscription cancellation."""
    timestamp = datetime.now().strftime('%d %b %Y, %H:%M')
    rows = [
        ('Customer', customer_email),
        ('Plan', plan_description),
        ('Cancelled at', timestamp),
    ]
    html = _wrap_html('Subscription Cancelled', f'<h3 style="margin:0 0 8px;">A subscriber cancelled</h3>{_info_block(rows)}')
    text = f"Subscription Cancelled\n\n" + "\n".join(f"{l}: {v}" for l, v in rows) + "\n\nFat Big Quiz"

    return _send_email(ADMIN_EMAIL, f'[FBQ] Cancellation: {customer_email}', html, text)


def send_admin_payment_failed_notification(customer_email, plan_description, failure_reason=None):
    """Email 8: Notify admin of a failed payment."""
    timestamp = datetime.now().strftime('%d %b %Y, %H:%M')
    rows = [
        ('Customer', customer_email),
        ('Plan', plan_description),
        ('Time', timestamp),
    ]
    if failure_reason:
        rows.append(('Reason', failure_reason))
    html = _wrap_html('Payment Failed', f'<h3 style="margin:0 0 8px;">A renewal payment failed</h3>{_info_block(rows)}')
    text = f"Payment Failed\n\n" + "\n".join(f"{l}: {v}" for l, v in rows) + "\n\nFat Big Quiz"

    return _send_email(ADMIN_EMAIL, f'[FBQ] Payment failed: {customer_email}', html, text)

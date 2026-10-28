"""
Client for the centralised Marketing service (marketing.laurence.computer).

Provides helpers for creating campaigns, sending newsletters, and tracking
UTM links. All requests authenticate with X-API-Key.
"""
import os
import requests


def _headers():
    """Build auth headers from environment."""
    api_key = os.environ.get('MARKETING_SERVICE_API_KEY', '')
    return {'X-API-Key': api_key, 'Content-Type': 'application/json'}


def _base_url():
    """Return the marketing service base URL."""
    return os.environ.get('MARKETING_SERVICE_URL', 'https://marketing.laurence.computer')


def create_campaign(name, description='', campaign_type='newsletter'):
    """Create a new marketing campaign.

    Args:
        name: Campaign name.
        description: Optional description.
        campaign_type: 'newsletter' or 'multi-channel'.

    Returns:
        Campaign dict on success, None on failure.
    """
    try:
        resp = requests.post(
            f'{_base_url()}/api/marketing/campaigns',
            json={'name': name, 'description': description, 'campaign_type': campaign_type},
            headers=_headers(),
            timeout=10
        )
        if resp.status_code == 201:
            return resp.json()
        print(f'[MarketingService] create_campaign failed: {resp.status_code} {resp.text}')
        return None
    except Exception as exc:
        print(f'[MarketingService] create_campaign error: {exc}')
        return None


def create_newsletter(subject, body_html, subscriber_list_id=None, campaign_id=None):
    """Create a newsletter draft.

    Args:
        subject: Email subject line.
        body_html: HTML body content.
        subscriber_list_id: Optional subscriber list identifier.
        campaign_id: Optional campaign to attach this newsletter to.

    Returns:
        Newsletter dict on success, None on failure.
    """
    try:
        payload = {
            'subject': subject,
            'body_html': body_html,
        }
        if subscriber_list_id:
            payload['subscriber_list_id'] = subscriber_list_id
        if campaign_id:
            payload['campaign_id'] = campaign_id

        resp = requests.post(
            f'{_base_url()}/api/marketing/newsletters',
            json=payload,
            headers=_headers(),
            timeout=10
        )
        if resp.status_code == 201:
            return resp.json()
        print(f'[MarketingService] create_newsletter failed: {resp.status_code} {resp.text}')
        return None
    except Exception as exc:
        print(f'[MarketingService] create_newsletter error: {exc}')
        return None


def send_newsletter(newsletter_id):
    """Trigger a newsletter send to its subscriber list.

    Args:
        newsletter_id: ID of the newsletter to send.

    Returns:
        Result dict on success, None on failure.
    """
    try:
        resp = requests.post(
            f'{_base_url()}/api/marketing/newsletters/{newsletter_id}/send',
            headers=_headers(),
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
        print(f'[MarketingService] send_newsletter failed: {resp.status_code} {resp.text}')
        return None
    except Exception as exc:
        print(f'[MarketingService] send_newsletter error: {exc}')
        return None


def get_campaign_stats(campaign_id):
    """Fetch performance statistics for a campaign.

    Args:
        campaign_id: Campaign ID.

    Returns:
        Stats dict on success, None on failure.
    """
    try:
        resp = requests.get(
            f'{_base_url()}/api/marketing/campaigns/{campaign_id}/stats',
            headers=_headers(),
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        print(f'[MarketingService] get_campaign_stats failed: {resp.status_code} {resp.text}')
        return None
    except Exception as exc:
        print(f'[MarketingService] get_campaign_stats error: {exc}')
        return None

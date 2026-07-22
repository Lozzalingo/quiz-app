"""
Create all Stripe products and prices for Fat Big Quiz.

Usage:
    STRIPE_SECRET_KEY=sk_test_... python scripts/create_stripe_products.py
    STRIPE_SECRET_KEY=sk_test_... python scripts/create_stripe_products.py --dry-run

Outputs a JSON mapping of plan keys to Stripe price IDs for use in the app.
"""
import os
import sys
import json
import math

# Add parent dir to path so we can run from quiz_app/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
if not stripe.api_key:
    print('Error: STRIPE_SECRET_KEY env var required')
    sys.exit(1)

DRY_RUN = '--dry-run' in sys.argv

# ===== Pricing definitions =====

TEAM_TIERS = [5, 10, 20, 50, 100]

# Event one-off prices (in pence)
EVENT_PRICES = {
    5: 499,
    10: 699,
    20: 999,
    50: 1599,
    100: 2399,
}

# Pro monthly prices (in pence) - [games_per_month][max_teams]
PRO_MONTHLY_PRICES = {
    1:  {5: 299, 10: 499, 20: 799, 50: 1399, 100: 2199},
    4:  {5: 999, 10: 1499, 20: 2199, 50: 3499, 100: 5499},
    8:  {5: 1699, 10: 2499, 20: 3699, 50: 5999, 100: 8999},
    16: {5: 2799, 10: 3999, 20: 5999, 50: 9499, 100: 14499},
    32: {5: 4499, 10: 6499, 20: 9499, 50: 14999},  # 100 = contact us
}

YEARLY_DISCOUNT = 0.8  # 20% off


def create_product(name, description, metadata=None):
    """Create a Stripe product."""
    if DRY_RUN:
        print(f'  [DRY RUN] Would create product: {name}')
        return {'id': f'prod_dry_run_{name.replace(" ", "_").lower()}'}

    product = stripe.Product.create(
        name=name,
        description=description,
        metadata=metadata or {},
    )
    print(f'  Created product: {name} ({product.id})')
    return product


def create_price(product_id, amount_pence, recurring=None, metadata=None):
    """Create a Stripe price."""
    if DRY_RUN:
        interval = recurring.get('interval', 'one_time') if recurring else 'one_time'
        print(f'  [DRY RUN] Would create price: {amount_pence}p {interval}')
        return {'id': f'price_dry_run_{amount_pence}_{interval}'}

    params = {
        'product': product_id,
        'unit_amount': amount_pence,
        'currency': 'gbp',
        'metadata': metadata or {},
    }
    if recurring:
        params['recurring'] = recurring

    price = stripe.Price.create(**params)
    print(f'  Created price: {amount_pence}p ({price.id})')
    return price


def main():
    price_map = {}

    # ===== Event products =====
    print('\n=== Event (one-off) products ===')
    for teams, amount in EVENT_PRICES.items():
        product = create_product(
            name=f'Fat Big Quiz - Event ({teams} teams)',
            description=f'One-off quiz game for up to {teams} teams. Includes custom branding and CSV export.',
            metadata={'type': 'event', 'max_teams': str(teams)},
        )
        price = create_price(
            product['id'], amount,
            metadata={'type': 'event', 'max_teams': str(teams)},
        )
        key = f'event_{teams}'
        price_map[key] = {
            'price_id': price['id'],
            'product_id': product['id'],
            'amount': amount,
            'max_teams': teams,
        }

    # ===== Pro subscription products =====
    print('\n=== Pro subscription products ===')
    for games, team_prices in PRO_MONTHLY_PRICES.items():
        for teams, monthly_amount in team_prices.items():
            # Monthly
            product = create_product(
                name=f'Fat Big Quiz Pro - {games}/month, {teams} teams',
                description=f'{games} quizzes per month, up to {teams} teams each. Custom branding, CSV export.',
                metadata={'type': 'pro', 'games_per_month': str(games), 'max_teams': str(teams)},
            )

            monthly_price = create_price(
                product['id'], monthly_amount,
                recurring={'interval': 'month'},
                metadata={'type': 'pro_monthly', 'games_per_month': str(games), 'max_teams': str(teams)},
            )

            monthly_key = f'pro_monthly_{games}g_{teams}t'
            price_map[monthly_key] = {
                'price_id': monthly_price['id'],
                'product_id': product['id'],
                'amount': monthly_amount,
                'games_per_month': games,
                'max_teams': teams,
            }

            # Yearly (same product, different price)
            yearly_amount = math.ceil(monthly_amount * 12 * YEARLY_DISCOUNT)
            yearly_price = create_price(
                product['id'], yearly_amount,
                recurring={'interval': 'year'},
                metadata={'type': 'pro_yearly', 'games_per_month': str(games), 'max_teams': str(teams)},
            )

            yearly_key = f'pro_yearly_{games}g_{teams}t'
            price_map[yearly_key] = {
                'price_id': yearly_price['id'],
                'product_id': product['id'],
                'amount': yearly_amount,
                'games_per_month': games,
                'max_teams': teams,
            }

    # ===== Output =====
    print(f'\n=== Summary ===')
    print(f'Total prices created: {len(price_map)}')
    print(f'  Event: {len([k for k in price_map if k.startswith("event_")])}')
    print(f'  Pro Monthly: {len([k for k in price_map if k.startswith("pro_monthly_")])}')
    print(f'  Pro Yearly: {len([k for k in price_map if k.startswith("pro_yearly_")])}')

    # Save to file
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stripe_prices.json')
    with open(output_path, 'w') as f:
        json.dump(price_map, f, indent=2)
    print(f'\nPrice map saved to: {output_path}')

    if DRY_RUN:
        print('\n(DRY RUN - nothing was created in Stripe)')


if __name__ == '__main__':
    main()

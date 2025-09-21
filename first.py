from flask import Flask, request, jsonify, session as flask_session, redirect, url_for
import stripe
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_fallback_secret_key")

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Define your product packages and Stripe price IDs
PRODUCTS = {
    'basic': 'price_1S9xxxBasicID',
    'premium': 'price_1S9xxxPremiumID'
}

@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    try:
        data = request.json
        amount = data['amount']
        currency = data.get('currency', 'usd')
        package = data.get('package', 'unknown')

        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata={'package': package},
            automatic_payment_methods={'enabled': True},
        )

        return jsonify({'clientSecret': intent.client_secret}), 200
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    data = request.json
    package = data.get('package')
    email = data.get('email')
    price_id = PRODUCTS.get(package)

    if not price_id:
        return jsonify({"error": "Invalid package"}), 400

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='subscription',
        customer_email=email,
        success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('payment_cancel', _external=True),
    )

    return jsonify({'checkout_url': checkout_session.url})

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    signature = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(payload, signature, WEBHOOK_SECRET)
    except ValueError:
        return '', 400
    except stripe.error.SignatureVerificationError:
        return '', 400

    if event['type'] == 'checkout.session.completed':
        stripe_session = event['data']['object']
        email = stripe_session.get('customer_email')
        # TODO: Mark user as premium in DB

    return '', 200

@app.route('/premium-content')
def premium_content():
    if not flask_session.get('is_premium'):
        return jsonify({"error": "You must purchase to access"}), 403
    return jsonify({"content": "Your premium videos/listings go here"})

@app.route('/payment-success')
def payment_success():
    flask_session['is_premium'] = True
    return "Payment success! You are now a premium member."

@app.route('/payment-cancel')
def payment_cancel():
    return "Payment cancelled. Try again."

if __name__ == '__main__':
    app.run(port=5000, debug=True)

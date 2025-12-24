import os
import stripe
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore

# Initialize the Admin SDK once at the top level
initialize_app()

@https_fn.on_request(
    region="europe-west1",
    secrets=["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"],
    cors=options.CorsOptions(
        cors_origins="*",
        cors_methods=["POST"],
    ),
)
def stripe_webhook(req: https_fn.Request) -> https_fn.Response:
    """
    Handle Stripe webhook events.
    When a purchase is complete, it creates/updates a user license in Firestore.
    """
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    if not stripe.api_key or not webhook_secret:
        return https_fn.Response("Missing required secrets", status=500)

    payload = req.get_data(as_text=True)
    sig_header = req.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return https_fn.Response("Invalid payload or signature", status=400)

    # Logic for successful checkout
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_details", {}).get("email")

        if not customer_email:
            return https_fn.Response("No customer email in session", status=400)

        db = firestore.client()
        license_ref = db.collection("licenses").document(customer_email)

        # We set is_paid to True. We don't set hardware_id yet; 
        # that happens when the user first runs the CLI.
        license_ref.set({"is_paid": True}, merge=True)

        return https_fn.Response(f"License updated for {customer_email}", status=200)

    return https_fn.Response(f"Unhandled event: {event['type']}", status=200)


@https_fn.on_request(
    region="europe-west1",
    cors=options.CorsOptions(
        cors_origins="*",
        cors_methods=["POST"],
    ),
)
def verify_license(req: https_fn.Request) -> https_fn.Response:
    """
    Called by the Zest CLI to verify or link a machine to a license.
    Expects JSON: {"email": "user@example.com", "hardware_id": "unique_hw_string"}
    """
    try:
        data = req.get_json()
    except Exception:
        return https_fn.Response("Invalid JSON", status=400)

    email = data.get("email")
    hw_id = data.get("hardware_id")

    if not email or not hw_id:
        return https_fn.Response("Missing email or hardware_id", status=400)

    db = firestore.client()
    doc_ref = db.collection("licenses").document(email)
    doc = doc_ref.get()

    if not doc.exists:
        return https_fn.Response("No license found for this email", status=404)

    license_data = doc.to_dict()
    
    # If the license is paid but no hardware_id is linked yet, link it now.
    if not license_data.get("hardware_id"):
        doc_ref.update({"hardware_id": hw_id})
        return https_fn.Response("License successfully linked to this machine", status=200)

    # If a hardware_id is already linked, it must match the current machine.
    if license_data.get("hardware_id") == hw_id:
        return https_fn.Response("Verified", status=200)
    else:
        return https_fn.Response("License is already tied to a different machine", status=403)
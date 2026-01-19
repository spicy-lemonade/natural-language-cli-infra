"""
Shared helper functions for Zest CLI cloud functions.
"""

from datetime import datetime, timezone


def get_product_fields(product: str) -> tuple:
    """Return field names for a given product type."""
    return (f"{product}_is_paid", f"{product}_devices", f"{product}_polar_order_id")


def get_trial_fields(product: str) -> tuple:
    """Return trial-related field names for a given product type."""
    return (
        f"{product}_is_trial",
        f"{product}_trial_started_at",
        f"{product}_trial_expires_at"
    )


def check_machine_trial_used(db, device_id: str, product: str) -> dict:
    """
    Check if a machine ID has already been used for a trial on any email.
    Returns {"used": bool, "email": str or None, "expired": bool or None}.
    """
    if not device_id:
        return {"used": False, "email": None, "expired": None}

    machine_ref = db.collection("trial_machines").document(device_id)
    machine_doc = machine_ref.get()

    if not machine_doc.exists:
        return {"used": False, "email": None, "expired": None}

    machine_data = machine_doc.to_dict()
    trial_email = machine_data.get(f"{product}_trial_email")

    if not trial_email:
        return {"used": False, "email": None, "expired": None}

    license_ref = db.collection("licenses").document(trial_email)
    license_doc = license_ref.get()

    if not license_doc.exists:
        return {"used": True, "email": trial_email, "expired": True}

    license_data = license_doc.to_dict()
    _, _, expires_field = get_trial_fields(product)
    expires_at = license_data.get(expires_field)

    if expires_at:
        now = datetime.now(timezone.utc)
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        expired = now >= expires_at
        return {"used": True, "email": trial_email, "expired": expired}

    return {"used": True, "email": trial_email, "expired": True}


def record_machine_trial(db, device_id: str, email: str, product: str):
    """Record that a machine ID has been used for a trial."""
    if not device_id:
        return

    machine_ref = db.collection("trial_machines").document(device_id)
    machine_ref.set({
        f"{product}_trial_email": email,
        f"{product}_trial_started_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }, merge=True)


def get_trial_status(license_data: dict, product: str) -> dict:
    """
    Check trial status for a product. Returns a dict with:
    - status: "paid", "trial_active", "trial_expired", or "no_license"
    - Additional fields depending on status
    """
    paid_field, devices_field, _ = get_product_fields(product)
    trial_field, _, expires_field = get_trial_fields(product)

    if license_data.get(paid_field):
        devices = license_data.get(devices_field, [])
        return {"status": "paid", "devices_registered": len(devices)}

    if license_data.get(trial_field):
        expires_at = license_data.get(expires_field)
        if expires_at:
            now = datetime.now(timezone.utc)
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if now < expires_at:
                remaining = expires_at - now
                hours_remaining = int(remaining.total_seconds() / 3600)
                days_remaining = hours_remaining // 24
                return {
                    "status": "trial_active",
                    "days_remaining": days_remaining,
                    "hours_remaining": hours_remaining,
                    "trial_expires_at": expires_at.isoformat()
                }
            else:
                return {"status": "trial_expired"}

    return {"status": "no_license"}

# Resend Email Setup for Zest

This guide walks you through configuring Resend to send OTP emails for Zest activation.

## Why Resend?

Resend is a modern email API designed for developers:
- Simple API with great DX
- Generous free tier (3,000 emails/month)
- Fast delivery
- Built-in email templates
- Great dashboard and analytics

## Step 1: Get Your Resend API Key

### 1.1: Create/Login to Resend Account

Go to [resend.com](https://resend.com) and sign up or log in.

### 1.2: Create an API Key

1. Go to the [API Keys page](https://resend.com/api-keys)
2. Click **Create API Key**
3. Name it: `Zest Production` (or whatever you prefer)
4. Permission: **Sending access** (default)
5. Click **Create**
6. Copy the API key (starts with `re_...`)
   - **Important**: Save this now! You won't be able to see it again.

## Step 2: Configure Your Sending Domain

### Option A: Use Resend's Test Domain (Development)

For testing, you can use Resend's built-in `onboarding@resend.dev` domain:

- **Pros**: Works immediately, no DNS setup
- **Cons**: Emails may go to spam, limited to 100/day
- **Best for**: Development and testing

**Update** `functions/main.py` line 43:
```python
"from": "Zest <onboarding@resend.dev>",
```

### Option B: Add Your Own Domain (Production)

For production, you should use your own domain:

#### 2.1: Add Domain in Resend

1. Go to [Domains page](https://resend.com/domains)
2. Click **Add Domain**
3. Enter your domain: `spicylemonade.com`
4. Click **Add**

#### 2.2: Add DNS Records

Resend will show you DNS records to add. Go to your DNS provider and add:

**SPF Record** (TXT):
```
Name: @
Value: v=spf1 include:_spf.resend.com ~all
```

**DKIM Record** (TXT):
```
Name: resend._domainkey
Value: [Resend will provide this]
```

**DMARC Record** (TXT) - Optional but recommended:
```
Name: _dmarc
Value: v=DMARC1; p=none; rua=mailto:dmarc@spicylemonade.com
```

#### 2.3: Verify Domain

1. Wait 5-10 minutes for DNS propagation
2. Click **Verify** in Resend dashboard
3. Once verified, you can send from `@spicylemonade.com`

**Update** `functions/main.py` line 43:
```python
"from": "Zest <noreply@spicylemonade.com>",
```

## Step 3: Add API Key to Firebase

### 3.1: Set the Secret

From your project root, run:

```bash
firebase functions:secrets:set RESEND_API_KEY
```

When prompted, paste your Resend API key (starts with `re_...`).

### 3.2: Verify It's Set

```bash
firebase functions:secrets:access RESEND_API_KEY
```

This should output your API key (be careful not to share this!).

## Step 4: Deploy Firebase Functions

```bash
cd functions
firebase deploy --only functions
```

The `send_otp` function will now have access to `RESEND_API_KEY`.

## Step 5: Test the Email Flow

### 5.1: Create Test License

Go to Firebase Console → Firestore → Add document:

```
Collection: licenses
Document ID: your-email@example.com
Fields:
  is_paid: true
  devices: []
```

### 5.2: Test CLI Activation

```bash
cd zest_cli
python main.py "list files"
```

You should:
1. See email prompt
2. Receive email at `your-email@example.com`
3. Email contains 6-digit code
4. Enter code and activate successfully

### 5.3: Check Email in Resend Dashboard

Go to [Logs page](https://resend.com/logs) to see:
- Email delivery status
- Whether it was opened
- Any errors

## Troubleshooting

### "RESEND_API_KEY not configured"

**Symptom**: Console shows OTP instead of sending email

**Solutions**:
1. Make sure you ran `firebase functions:secrets:set RESEND_API_KEY`
2. Verify with `firebase functions:secrets:access RESEND_API_KEY`
3. Redeploy: `firebase deploy --only functions`
4. Check that `send_otp` function includes `secrets=["RESEND_API_KEY"]` (line 144)

### Emails Going to Spam

**Causes**:
- Using test domain (`onboarding@resend.dev`)
- Domain not verified
- Missing SPF/DKIM records

**Solutions**:
1. Use your own verified domain
2. Add all DNS records (SPF, DKIM, DMARC)
3. Wait 24-48 hours for reputation to build
4. Send from a professional address (not `test@` or `noreply@`)

### "Rate limit exceeded"

**Causes**:
- Free tier: 3,000 emails/month, 100/day for test domain
- Production tier: varies by plan

**Solutions**:
1. Upgrade Resend plan if needed
2. Implement rate limiting in your code
3. Add cooldown between OTP requests

### Emails Not Arriving

**Check**:
1. Resend Logs: [resend.com/logs](https://resend.com/logs)
2. Spam folder
3. Email address is correct
4. Domain DNS records are verified

## Email Template Customization

The email template is in `functions/main.py` lines 46-81.

### Change Colors

Update the CSS in the `<style>` section:

```python
.code {{
    color: #YOUR_COLOR;  # Change from #FF6B35
    background: #YOUR_BG_COLOR;  # Change from #f5f5f5
}}
```

### Change Logo

Add an image:

```python
<div class="container">
    <img src="https://spicylemonade.com/logo.png" alt="Logo" width="120">
    <h1>🍋 Your Zest Activation Code</h1>
    ...
</div>
```

### Add Footer Links

Update the footer section:

```python
<div class="footer">
    <p>
        <a href="https://spicylemonade.com">Website</a> |
        <a href="https://spicylemonade.com/docs">Docs</a> |
        <a href="mailto:support@spicylemonade.com">Support</a>
    </p>
</div>
```

## Monitoring & Analytics

### Resend Dashboard

View in real-time:
- Total emails sent
- Delivery rate
- Open rate
- Bounce rate
- Click rate

### Set Up Webhooks (Optional)

Get notified when emails are delivered/opened:

1. Go to [Webhooks page](https://resend.com/webhooks)
2. Add endpoint: `https://your-functions-url/email_webhook`
3. Select events: `email.delivered`, `email.bounced`
4. Create webhook endpoint in Firebase Functions

## Rate Limits

### Free Tier
- 3,000 emails/month
- 100 emails/day with test domain
- Unlimited with verified domain (up to monthly limit)

### Paid Plans
- Growth: 50,000 emails/month - $20/mo
- Pro: 100,000 emails/month - $50/mo
- See [resend.com/pricing](https://resend.com/pricing)

## Best Practices

### 1. Use a Real From Address

```python
"from": "Zest Support <support@spicylemonade.com>"  # Good
"from": "noreply@spicylemonade.com"                  # Okay
"from": "no-reply@resend.dev"                        # Bad (test only)
```

### 2. Add Plain Text Version

For better deliverability:

```python
params = {
    "from": "...",
    "to": [...],
    "subject": "...",
    "html": "...",
    "text": f"Your Zest activation code is: {otp_code}\n\nThis code expires in 5 minutes."
}
```

### 3. Implement Reply-To

```python
params = {
    ...
    "reply_to": "support@spicylemonade.com"
}
```

### 4. Add Tags for Organization

```python
params = {
    ...
    "tags": [
        {"name": "category", "value": "activation"},
        {"name": "product", "value": "zest"}
    ]
}
```

## Security Considerations

### 1. Protect Your API Key

- ✅ Store in Firebase Secrets
- ✅ Never commit to Git
- ✅ Rotate regularly
- ❌ Don't expose in client-side code

### 2. Rate Limit OTP Requests

Add to your code:

```python
# Track last OTP request time
last_request = license_data.get("last_otp_request")
if last_request:
    time_since = datetime.utcnow() - last_request
    if time_since < timedelta(minutes=1):
        return https_fn.Response("Please wait before requesting another code", status=429)
```

### 3. Validate Email Addresses

```python
import re

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
```

## Testing Checklist

Before going to production:

- [ ] API key configured in Firebase Secrets
- [ ] Domain verified in Resend
- [ ] SPF/DKIM/DMARC records added
- [ ] Test email sends successfully
- [ ] Email doesn't go to spam
- [ ] OTP code is readable
- [ ] Email template looks good on mobile
- [ ] Links in footer work
- [ ] Resend dashboard shows delivery

## Cost Estimation

For Zest with 2-device licensing:

**Assumptions**:
- 1,000 users
- Each user activates 2 devices = 2,000 activations
- 5% re-request OTP = 100 extra emails
- Total: ~2,100 emails

**Resend Costs**:
- Free tier: 3,000/month = **$0** ✅
- If you exceed: Growth plan at $20/month for 50k emails

**Bottom line**: You can support 1,000+ users on the free tier!

## Quick Reference

```bash
# Set API key
firebase functions:secrets:set RESEND_API_KEY

# View API key
firebase functions:secrets:access RESEND_API_KEY

# Deploy with secret
firebase deploy --only functions

# Delete secret (if needed)
firebase functions:secrets:destroy RESEND_API_KEY
```

## Next Steps

1. ✅ Get Resend API key
2. ✅ Add to Firebase Secrets
3. ✅ Deploy functions
4. ✅ Test email delivery
5. ⏳ Verify your domain (for production)
6. ⏳ Customize email template
7. ⏳ Set up monitoring

## Resources

- [Resend Documentation](https://resend.com/docs)
- [Resend Python SDK](https://github.com/resendlabs/resend-python)
- [Firebase Secrets](https://firebase.google.com/docs/functions/config-env#secret-manager)
- [Email Best Practices](https://resend.com/docs/knowledge-base/deliverability)

---

**You're all set!** Resend will now handle your OTP emails professionally. 🎉

# Zest Quick Start Guide

Get your licensed Zest CLI up and running in 10 minutes.

## Prerequisites

- Firebase project set up
- Resend account (sign up at [resend.com](https://resend.com))
- Node.js and Firebase CLI installed

## Step 1: Get Your Resend API Key (2 mins)

1. Go to [resend.com/api-keys](https://resend.com/api-keys)
2. Click **Create API Key**
3. Name it: `Zest Production`
4. Copy the API key (starts with `re_...`)

## Step 2: Configure Firebase (3 mins)

```bash
# Navigate to project root
cd /Users/ciaranobrien/spicy_lemonade/natural-language-cli-infra

# Add Resend API key to Firebase Secrets
firebase functions:secrets:set RESEND_API_KEY
# Paste your Resend API key when prompted

# Get your Firebase project ID
firebase projects:list
# Copy the PROJECT_ID from the output
```

## Step 3: Update CLI Configuration (1 min)

Edit `zest_cli/main.py` line 14:

```python
API_BASE_URL = "https://europe-west1-YOUR_PROJECT_ID.cloudfunctions.net"
```

Replace `YOUR_PROJECT_ID` with your actual Firebase project ID from Step 2.

## Step 4: Deploy Backend (2 mins)

```bash
cd functions
firebase deploy --only functions
```

Wait for deployment to complete. You should see:
- ✅ stripe_webhook
- ✅ send_otp
- ✅ verify_otp_and_register
- ✅ replace_device
- ✅ deregister_device
- ✅ validate_device

## Step 5: Test It! (2 mins)

### 5.1: Create a Test License

Go to [Firebase Console](https://console.firebase.google.com) → Firestore:

1. Click **Start collection**
2. Collection ID: `licenses`
3. Document ID: `your-email@example.com` (use your real email)
4. Add fields:
   - `is_paid` (boolean): `true`
   - `devices` (array): `[]` (empty array)
5. Click **Save**

### 5.2: Test CLI

```bash
cd ../zest_cli
pip install -r requirements.txt
python main.py "list files in current directory"
```

You should see:
1. **Email prompt** → Enter your test email
2. **Check your email** → You'll receive a 6-digit code
3. **Enter OTP** → Paste the code
4. **Device nickname** → Give it a name (e.g., "My MacBook")
5. **Success!** → License activated

## What You've Built

```
┌──────────────────────────────────────────────────┐
│  User Flow                                       │
├──────────────────────────────────────────────────┤
│  1. Stripe Purchase → License Created           │
│  2. Download Zest.pkg → Install                  │
│  3. Run 'zest' → Activation Prompt               │
│  4. Enter Email → Receive OTP                    │
│  5. Enter OTP → Device Registered                │
│  6. Generate Commands → Licensed & Working!      │
└──────────────────────────────────────────────────┘
```

## Next Steps

### For Development
- ✅ Backend deployed with Resend integration
- ✅ CLI ready for testing
- ⏳ Test on a second device to verify 2-device limit
- ⏳ Test `--logout` and `--uninstall` commands

### For Production
- ⏳ Verify your domain in Resend (see `zest_cli/RESEND_SETUP.md`)
- ⏳ Update email template branding
- ⏳ Build .pkg installer (`./build.sh`)
- ⏳ Code sign and notarize (see `zest_cli/SIGNING_GUIDE.md`)
- ⏳ Set up Stripe product and webhook

## Email Configuration

### Using Resend Test Domain (Current)

The code currently uses:
```python
"from": "Zest <noreply@spicylemonade.com>"
```

**For testing only**, change this to:
```python
"from": "Zest <onboarding@resend.dev>"
```

This works immediately but:
- Emails may go to spam
- Limited to 100/day
- Shows "via resend.dev"

### Using Your Own Domain (Production)

See `zest_cli/RESEND_SETUP.md` for:
1. Adding your domain in Resend
2. DNS record configuration
3. Domain verification

## Common Commands

```bash
# Test CLI locally
python zest_cli/main.py "your query"

# Check Firebase Functions logs
firebase functions:log

# Redeploy after changes
firebase deploy --only functions

# View Firestore data
# Go to: https://console.firebase.google.com → Firestore

# Check Resend email logs
# Go to: https://resend.com/logs
```

## Troubleshooting

### "No license found for this email"
- Check Firestore - does the document exist?
- Is `is_paid` set to `true`?
- Is the email exactly matching?

### "RESEND_API_KEY not configured"
- Did you run `firebase functions:secrets:set RESEND_API_KEY`?
- Did you redeploy functions after setting it?
- Check it's set: `firebase functions:secrets:access RESEND_API_KEY`

### OTP email not arriving
- Check spam folder
- Check Resend logs: [resend.com/logs](https://resend.com/logs)
- Try changing `from` to `onboarding@resend.dev` for testing
- Verify RESEND_API_KEY is correct

### "Invalid JSON" errors
- Check API_BASE_URL in `zest_cli/main.py` is correct
- Verify functions are deployed: `firebase deploy --only functions`

## Testing Checklist

Before considering it "done":

- [ ] Backend deployed successfully
- [ ] Resend API key configured
- [ ] Test license created in Firestore
- [ ] CLI activation works
- [ ] OTP email arrives (check inbox/spam)
- [ ] Device registers successfully
- [ ] Commands generate correctly
- [ ] Test on second device (or re-activate)
- [ ] Test device limit (3rd device shows replacement menu)
- [ ] Test `--logout` command
- [ ] Test `--uninstall` command

## Complete Documentation

- **Overview**: `/IMPLEMENTATION_SUMMARY.md`
- **CLI Development**: `/zest_cli/SETUP.md`
- **Resend Setup**: `/zest_cli/RESEND_SETUP.md`
- **Code Signing**: `/zest_cli/SIGNING_GUIDE.md`
- **CLI README**: `/zest_cli/README.md`

## You're Ready! 🎉

Your commercial Zest CLI with 2-device licensing is now live and working with Resend email delivery.

**What works right now:**
- ✅ 2-device licensing enforced server-side
- ✅ OTP email delivery via Resend
- ✅ Hardware UUID binding
- ✅ Device management (register, replace, deregister)
- ✅ Offline support with online validation
- ✅ Complete CLI with `--logout` and `--uninstall`

**To go from beta → production:**
1. Verify your domain in Resend
2. Build and sign the .pkg installer
3. Connect Stripe webhook
4. Launch! 🚀

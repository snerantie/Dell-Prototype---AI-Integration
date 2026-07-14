# Real WhatsApp Integration Guide

*How to move EduConnect AI Tutor from the browser simulator to real Meta WhatsApp Business*

## Overview

The code is **production-ready** — `app/providers/whatsapp.py` already implements Meta's Cloud API contract. To go live, you need to:

1. Sign up for a Meta Business account
2. Register a phone number + generate an access token
3. Configure the webhook to point at the Render deployment
4. Set 4 environment variables on Render

**Time to live:** ~2 hours if you have a personal Facebook account. ~1–14 days if you need full business verification (only required beyond 5 test recipients).

## Prerequisites

- ✅ Render deployment already live at https://educonnect-tutor.onrender.com (or your equivalent)
- ✅ A personal Facebook account (business verification NOT required for the 5-recipient test phase)
- ✅ A phone number that is NOT currently used on personal WhatsApp (Meta will assign one, or you supply your own for production)

## Step 1 — Create a Meta Developer app (10 min)

1. Go to https://developers.facebook.com/apps and click **Create App**
2. Select **"Business"** as the app type
3. Fill in app display name (e.g. "EduConnect Tutor") and contact email
4. Click **Create App**
5. On the app dashboard, find **WhatsApp** in the product list → click **Set Up**

Meta gives you a **test phone number** automatically. You can start sending messages to test recipients immediately, no business verification needed.

## Step 2 — Get the three credentials (5 min)

In the Meta app dashboard → **WhatsApp → API Setup**:

- **Phone Number ID** — long numeric ID (this is Meta's ID for your test number)
- **Access Token** (temporary, 24-hour expiry — good for setup; regenerate a permanent one via System User later)
- **WhatsApp Business Account ID** — needed for later template creation

Copy these three values.

## Step 3 — Add test recipient phone numbers (5 min)

In the API Setup page, under "To" (recipient) → click **Add phone number** → enter phone numbers of testers (Lead's phone, daughter, Dell team, up to 5 total). Meta sends each a WhatsApp verification code to confirm.

**Only these 5 numbers can message the test number until you complete business verification.**

## Step 4 — Configure the webhook on Meta (10 min)

In the app dashboard → **WhatsApp → Configuration → Webhook**:

- **Callback URL:** `https://educonnect-tutor.onrender.com/webhook/whatsapp` (or your Render URL)
- **Verify Token:** any secret string you choose — e.g. `educonnect-webhook-2026`

Click **Verify and Save**. Meta hits your webhook endpoint with the verify token. Our code (in `app/channels/whatsapp.py`) responds correctly if `WHATSAPP_VERIFY_TOKEN` env var matches.

If verify fails, check the Render logs for the incoming request — 99% of the time it's a whitespace/typo mismatch.

**Subscribe to fields:** in the same webhook config, subscribe to **messages** events.

## Step 5 — Set 4 environment variables on Render (5 min)

Render dashboard → your EduConnect service → **Environment** tab → add these 4 variables:

| Key | Value | Where from |
|---|---|---|
| `WHATSAPP_PROVIDER` | `cloud` | Switches from mock to real Meta client |
| `WHATSAPP_PHONE_NUMBER_ID` | *(from Meta Step 2)* | The test phone number ID |
| `WHATSAPP_ACCESS_TOKEN` | *(from Meta Step 2)* | Start with the temporary token |
| `WHATSAPP_VERIFY_TOKEN` | *(same as Meta Step 4)* | Your chosen secret |

**Save Changes** → Render auto-redeploys (~30 sec).

## Step 6 — Test it live (2 min)

From a test recipient phone, open WhatsApp → send `Hi` to the Meta test number.

Expected:
- The Render app's `/webhook/whatsapp` endpoint receives the inbound message
- The tutor engine processes it (same code path as the browser simulator)
- The reply is sent back via Meta's Cloud API
- The test phone receives the WhatsApp greeting with 3 quick-reply buttons

If nothing happens:
1. Check Render logs — look for the incoming webhook POST
2. Check that `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN` are set correctly
3. Verify the webhook URL in Meta's config matches your Render URL exactly
4. Confirm the test recipient's phone was accepted in Step 3

## Health check endpoint

Once configured, hit https://educonnect-tutor.onrender.com/health/whatsapp — returns JSON showing whether all 4 env vars are present and the provider is `cloud`, not `mock`.

## Step 7 — Get a permanent access token (for production)

The temporary token expires in 24 hours. For production:

1. Meta app dashboard → **Business Settings** → **System Users**
2. Create a System User
3. Assign the WhatsApp permission with `whatsapp_business_messaging` scope
4. Generate a permanent access token
5. Update `WHATSAPP_ACCESS_TOKEN` on Render

## Beyond 5 recipients — business verification

To send to unlimited phone numbers (i.e. real launch), Meta requires **business verification**. This takes 1–14 days and needs:

- Company registration document (CIPC certificate for SA companies)
- Proof of business address (utility bill)
- Tax reference number
- Business phone (verified via call/SMS)

For the hackathon pitch phase, the 5-recipient test flow is enough. Business verification is a post-Dell-sponsorship step.

## Zero-rating with Vodacom (parallel track)

Zero-rating is a separate commercial conversation. Once you have a dedicated WhatsApp Business phone number, Vodacom can whitelist it so learners don't pay data. Timeline: 6–12 weeks of business development.

Precedents (Vodacom already zero-rates these educational services):
- DBE digital textbooks
- Siyavula
- Mindset Learn (some periods)

Your case: Grade 10-12 Maths tutoring with Dell sponsorship. Strong social impact angle.

## Message templates (for outbound-initiated messages)

For learner-initiated conversations (learner texts you first), **no template needed** — you can reply freely for 24 hours.

For business-initiated (e.g. "your USSD session moved here" handoff), submit templates to Meta:
- Category: **Utility** (education-aligned — cheaper per message than Marketing)
- Approval: 1–3 days
- Templates needed: `tutor_continue_from_ussd`, `weekly_exam_reminder`, `welcome_new_learner`

## What can go wrong

- **Webhook verification fails:** verify token mismatch. Regenerate on both sides, save on Render first.
- **Messages sent but no reply:** check the Render logs — probably an unhandled exception in the engine. Confirm `LLM_PROVIDER=dell` is also set (or accept mock replies for testing).
- **"Recipient not accepted":** you're outside the 5-recipient allowlist. Add them via the Meta app dashboard.
- **Render service asleep:** free tier sleeps after 15 min idle. First message wakes it up (~30 sec delay); subsequent messages are fast. Upgrade to $7/month "starter" tier removes the sleep entirely.

## Cost

| Component | Cost |
|---|---|
| Meta WhatsApp Business Cloud API | Free for first 1,000 conversations/month; then ~R0.10-0.50 per conversation depending on category |
| Render hosting | Free tier during pilot; $7/month for always-on production |
| Groq API (LLM) | Free during pilot; move to Dell AI Factory NIM for production |

**Pilot phase total: R0 / month.** Production estimate: R500-1000/month before Vodacom / Dell partnership subsidises.

## Repo references

- `app/providers/whatsapp.py` — `CloudWhatsAppClient` (already implements Meta's Cloud API)
- `app/channels/whatsapp.py` — webhook endpoints (`/webhook/whatsapp` GET verify + POST inbound)
- `app/config.py` — env var configuration

## Contact

Repo: https://github.com/snerantie/Dell-Prototype---AI-Integration/tree/feat/tutor-scaffold

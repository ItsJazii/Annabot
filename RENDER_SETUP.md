# Deploy Anna on Render

## Step 1: Create Render Account

1. Go to [https://render.com](https://render.com)
2. Sign up with your email or GitHub account

## Step 2: Create New Web Service

1. In your Render Dashboard, click **"New +"**
2. Select **"Web Service"**

## Step 3: Connect GitHub Repo

1. Find and click on **"ItsJazii / Annabot"**
2. Click **"Connect"**

## Step 4: Configure Service

1. **Name**: `anna-bot`
2. **Runtime**: `Python 3`
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `python main.py`
5. Click **"Create Web Service"**

## Step 5: Set Environment Variables

1. Click the **"Environment"** tab in your service dashboard
2. Add the following variables:
   - `BOT_TOKEN` — your Telegram bot token from @BotFather
   - `BOT_OWNER_ID` — your Telegram user ID
   - `OPENROUTER_API_KEY` — from openrouter.ai
   - `GROQ_API_KEY` — from console.groq.com
   - `CEREBRAS_API_KEY` — from cloud.cerebras.ai
   - `SUPABASE_URL` — your Supabase project URL (optional)
   - `SUPABASE_KEY` — your Supabase anon key (optional)
3. Click **"Save Changes"**

## Step 6: Deploy

1. Render will automatically deploy from your GitHub repo
2. Wait for the build to complete (1-2 minutes)
3. Check the logs — you should see: `Bot is running...`

## Step 7: Keep It Alive

Render free tier sleeps after 15 minutes of no web traffic. To keep Anna running 24/7:

1. Go to [https://uptimerobot.com](https://uptimerobot.com)
2. Sign up for free
3. Add a new HTTP(s) monitor pointing to your Render URL
4. Set monitoring interval to every 5 minutes

## Troubleshooting

**Bot not responding?**
- Check Render logs for errors
- Make sure all required env vars are set

**Render says "Service slept"?**
- UptimeRobot isn't set up correctly
- Check that the URL matches your Render URL exactly

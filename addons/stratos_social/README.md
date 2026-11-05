# Stratos Social Marketing — Phase 1 (Odoo 20 Community)

Compose once, publish to **Facebook Pages**, **Instagram Business** accounts, **YouTube** channels and **TikTok** accounts — now or on a schedule — from inside Odoo.

---

## 1. What is included

| # | Feature | Where in Odoo |
|---|---------|---------------|
| 1 | Connect Facebook Pages + linked Instagram Business accounts | Social Marketing › Accounts › **+ Meta** |
| 2 | Connect YouTube channels (Google login) | Social Marketing › Accounts › **+ YouTube** |
| 2b | Connect TikTok accounts (TikTok login) | Social Marketing › Accounts › **+ TikTok** |
| 3 | Quick Facebook/Instagram connect by pasting an access token (for testing) | Social Marketing › Accounts › **Token** |
| 4 | Compose a post: message, images (up to 10), link | Social Marketing › Posts › New |
| 5 | YouTube video: one video file, title, visibility (Public / Unlisted / Private), category, Made for Kids | Post form › YouTube (shown when a channel is selected) |
| 5b | TikTok video: who can view (no default — TikTok rule), allow Comment / Duet / Stitch, AI-generated label, commercial content disclosure (Your Brand / Branded Content), TikTok consent text | Post form › TikTok (shown when a TikTok account is selected) |
| 6 | Live preview (Facebook, Instagram, YouTube and TikTok style) | Right side of the post form |
| 7 | Checks before publishing (Instagram image, caption 2,200 chars, 30 hashtags; YouTube title 100 chars, one video) | Yellow box on the post form |
| 8 | Post Now / Schedule Later (published automatically every 5 minutes) | Post form › When |
| 9 | Content calendar — drag a draft or scheduled post to reschedule | Social Marketing › Content Calendar |
| 10 | Results per account with link to the live post; **Retry Failed** | Post form › Results tab |
| 11 | Failed post creates a To-Do activity for the responsible user | Activities |
| 12 | Campaigns (UTM), multi-company, chatter history | Post form › Organise |

**How one post goes to each platform**

| Platform | Uses | Message becomes |
|----------|------|-----------------|
| Facebook Page | Images (optional) + link | Post text |
| Instagram | Images (1–10, required) | Caption |
| YouTube | Video (exactly 1, required) + YouTube Title | Description; #hashtags become tags |
| TikTok | The same video (exactly 1, required) | Caption (max 2,200 characters) |

One post can go to all four: Facebook/Instagram take the images, YouTube and TikTok take the video.

TikTok processes videos in the background: the result shows **Processing** first and the scheduler updates it to **Posted** (with the link) or **Failed** (with TikTok's reason) within minutes.

**User rights** (Settings › Users › Social Marketing):

| Role | Can do |
|------|--------|
| User | Write, schedule and publish posts on connected accounts |
| Administrator | Also connect accounts, see tokens and change settings |

---

## 2. Install

1. Copy the `stratos_social` folder into your custom addons path.
2. Restart Odoo.
3. Apps › Update Apps List › search **Stratos Social Marketing** › Install.

**Requirement for Instagram:** Odoo must be on a **public https:// address** (e.g. `https://erp.stratos-hub.com`). Instagram downloads the images from Odoo; it cannot reach `localhost` or `http://`. Facebook works without this.

---

## 3. Create the Meta app (one time, by Stratos Hub)

1. Go to **developers.facebook.com** › My Apps › **Create App**.
2. Use case: **Manage everything on your Page** (and add **Instagram** › *API setup with Facebook login*). App type: **Business**.
3. App settings › Basic: copy **App ID** and **App Secret**.
4. Facebook Login for Business › Settings › **Valid OAuth Redirect URIs**: paste the URI shown in
   Odoo › Settings › Social Marketing (looks like `https://your-odoo/stratos_social/meta/callback`).
5. Permissions to request:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `business_management`
   - `instagram_basic`
   - `instagram_content_publish`

---

## 4. Connect accounts in Odoo

**Option A — Meta login (for real use)**
1. Odoo › Settings › Social Marketing: enter **App ID** and **App Secret** › Save.
2. Social Marketing › Accounts › **+ Meta**.
3. Log in to Facebook, tick your Page(s), allow the permissions.
4. You return to Odoo: the Facebook Page and its linked Instagram account appear.

**Option B — Access token (quick test, no app review needed)**
1. Open **Graph API Explorer** (developers.facebook.com/tools/explorer), select your app.
2. Add the six permissions above › **Generate Access Token** › select your Page.
3. Odoo › Social Marketing › Accounts › **Token** › paste › Connect Pages.

Page tokens obtained this way do not expire (when App ID and Secret are set in Settings). If a token stops working, the account turns red (**Needs Attention**) — press **Reconnect**.

---

## 5. Set up YouTube (one time, by Stratos Hub)

1. Go to **console.cloud.google.com** › create a project (e.g. *Stratos Social*).
2. APIs & Services › Library › enable **YouTube Data API v3**.
3. APIs & Services › **OAuth consent screen**: User type *External*, app name, support email, add scopes
   `youtube.upload` and `youtube.readonly`. Add your own Google account under **Test users**.
4. APIs & Services › Credentials › **Create OAuth client ID** › *Web application*.
   Under **Authorized redirect URIs** paste the URI shown in Odoo › Settings › Social Marketing › YouTube
   (looks like `https://your-odoo/stratos_social/google/callback`).
5. Copy **Client ID** and **Client Secret** into Odoo › Settings › Social Marketing › YouTube › Save.
6. Social Marketing › Accounts › **+ YouTube** › choose the Google account that owns the channel › Allow.

**Google rules to know before going live**

| # | Rule | What to do |
|---|------|------------|
| 1 | Videos uploaded through an **unaudited** API project are locked to **Private** | Use it in Private/Unlisted for testing; apply for the **YouTube API Services audit** (free, via Google's audit form) before posting publicly for clients |
| 2 | While the consent screen is in **Testing**, Google login expires after **7 days** (account turns red) | Press **Reconnect**, or set the consent screen to **In production** and complete Google verification |
| 3 | Daily upload quota: 10,000 units by default; one upload costs about 1,600 units → **about 6 videos per day** per Google project | Request a quota increase in Google Cloud if clients need more |
| 4 | Odoo's default upload limit is **128 MB** per file | For longer videos raise system parameter `web.max_file_upload_size` (bytes) and the Nginx `client_max_body_size` |

---

## 5b. Set up TikTok (one time, by Stratos Hub)

1. Go to **developers.tiktok.com** › Manage apps › **Connect an app** (register as an organisation: Stratos Hub).
2. Add products **Login Kit** and **Content Posting API**; turn on **Direct Post**.
3. Scopes: `user.info.basic` and `video.publish`.
4. Login Kit › **Redirect URI**: paste the URI shown in Odoo › Settings › Social Marketing › TikTok
   (looks like `https://your-odoo/stratos_social/tiktok/callback` — must be https).
5. Copy **Client Key** and **Client Secret** into Odoo › Settings › Social Marketing › TikTok › Save.
6. Social Marketing › Accounts › **+ TikTok** › log in to TikTok › Authorize.

**TikTok rules to know before going live**

| # | Rule | What to do |
|---|------|------------|
| 1 | Until TikTok **audits** your app, every video is posted as **Only me**, the TikTok account must be set to **Private**, and at most **5 accounts** can post per 24 hours | Test with *Only me*. Apply for the Direct Post audit in the TikTok developer portal; after approval tick **TikTok App Audited** in Odoo Settings to unlock Everyone / Friends / Followers |
| 2 | TikTok checks the posting screen during the audit | This module already follows TikTok's Content Sharing Guidelines (account name shown, privacy with no default, interactions unchecked, greyed out when the creator disabled them, commercial disclosure, consent text, processing notice) — record a short screen video of it for the audit form |
| 3 | About **15 posts per creator per day** through the API (shared with other tools) | Plan daily volume per client account |
| 4 | Login lasts 24 hours and renews automatically for a year; after that, or if access is removed in TikTok, the account turns red | Press **Reconnect** |
| 5 | Branded content (paid partnership) cannot be *Only me* | The post form blocks this combination |

---

## 6. Meta App Review — important before selling to clients

| Situation | Review needed? |
|-----------|----------------|
| Posting to Pages where **you** (or people added as app roles) are admins | **No** — works in Development mode |
| Posting to **clients'** Pages / Instagram from your app | **Yes** — submit App Review for the permissions above, and complete **Business Verification** for Stratos Hub |

Allow 2–6 weeks for review. Meta asks for a screen recording of the connect and publish flow — this module's screens can be used for that.

---

## 7. Limits in Phase 1

1. Facebook and Instagram: images only (JPEG / PNG — PNG is converted to JPEG for Instagram automatically). Facebook video and Instagram Reels come in Phase 2.
2. YouTube: video uploads only (YouTube has no API for community/image posts). Custom thumbnails come in Phase 2.
3. TikTok: video only (photo carousels come in Phase 2). Video length is checked by TikTok (the allowed maximum is shown on the TikTok account).
4. Instagram: 1–10 images per post; links in captions are not clickable (Instagram rule).
5. No comments inbox or analytics yet — planned for Phases 2–3.

---

## 8. Technical notes

* Models: `stratos.social.account`, `stratos.social.post`, `stratos.social.live.post` (one result per account), wizard `stratos.social.token.wizard`.
* Scheduler: *Social Marketing: Publish scheduled posts* (every 5 minutes).
* Every Meta API call is signed with `appsecret_proof` when the App Secret is set.
* YouTube: refresh token is stored on the account (administrators only); the access token is refreshed automatically before it expires; uploads use YouTube's resumable upload.
* TikTok: Direct Post with FILE_UPLOAD (single upload up to 64 MB, otherwise 10 MB chunks); creator info is re-read right before every post; processing results are polled by the same scheduler.
* Graph API version is a setting (default `v25.0`) — raise it in Settings when Meta retires a version; no code change needed.
* Tests: `odoo-bin -d <db> -i stratos_social --test-enable --test-tags /stratos_social` (Meta, Google and TikTok APIs are mocked; 32 tests).

## 9. Odoo 20 edition — what differs from the Odoo 19 edition

Functions and screens are the same. Changes needed for Odoo 20:

| # | Odoo 20 change | What this module does |
|---|----------------|-----------------------|
| 1 | Access rights and record rules merged into one model, `ir.access` | `security/ir.access.csv` replaces `ir.model.access.csv` and the multi-company `ir.rule` records |
| 2 | System parameters use typed methods (`get_str`, `get_bool`, `set_str`…) | All settings are read with the typed methods |
| 3 | Attachments no longer take base64 `datas`; file content is a binary object (`raw`) | Images and videos are read with `bytes(attachment.raw)`; converted JPEGs are saved through `raw` |
| 4 | Toolbar buttons in list/kanban are called as record methods | Connect buttons are plain record methods |
| 5 | Narrower toolbar | Account buttons shortened to **+ Meta**, **+ YouTube**, **+ TikTok**, **Token** |
| 6 | Icons are Material Symbols instead of Font Awesome | Button icons use the new names (`add`, `key`, `campaign`, `fact_check`) |

Version: `20.0.1.2.0`. Install only on Odoo 20; use the `19.0.x` package for Odoo 19.

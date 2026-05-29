# Streamlit Cloud Deployment Guide

## Prerequisites
- GitHub account with your code pushed
- Google Cloud credentials with access to Google Sheets API
- Streamlit Community Cloud account

## Deployment Steps

### 1. Prepare Your Repository
```bash
# Ensure all files are committed and pushed to GitHub
git add .
git commit -m "Add deployment files"
git push
```

Your repo structure should have:
- `requirements.txt` ✅
- `.streamlit/config.toml` ✅
- `.streamlit/secrets.toml.example` (template only)
- `Clientes.py` (main app)
- `pages/` folder
- `utils.py`

### 2. Set Up Google Sheets Credentials

#### Option A: Using Service Account (Recommended)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Google Sheets API and Google Drive API
4. Create a **Service Account**:
   - Go to "Service Accounts"
   - Create new service account
   - Generate a JSON key
   - Download the key file

5. Share your Google Sheet with the service account email
   - Copy the `client_email` from the JSON key
   - Open your Sheet → Share → Add the email

#### Option B: Using OAuth 2.0 (Current Method)
1. Keep using your current `credentials.json`
2. Generate a refresh token from `token.json`
3. Convert to Streamlit Secrets format

### 3. Add Secrets to Streamlit Cloud

1. Go to [Streamlit Cloud Dashboard](https://share.streamlit.io)
2. Click your app → **Settings** → **Secrets**
3. Paste the credentials as TOML:

```toml
[google_sheets_credentials]
type = "authorized_user"
client_id = "your_client_id.apps.googleusercontent.com"
client_secret = "your_client_secret"
refresh_token = "your_refresh_token"
```

### 4. Deploy on Streamlit Cloud

1. Go to [Streamlit Community Cloud](https://share.streamlit.io)
2. Click "New app"
3. Select your GitHub repository
4. Branch: `main` (or your default branch)
5. Main file path: `Clientes.py`
6. Click "Deploy"

### 5. Environment Variables (Optional)

If needed, you can also add environment variables in Streamlit Cloud settings:
- Click **Settings** on your app
- Add under "Secrets" or use the advanced section

## Troubleshooting

### Authentication Fails
- Verify credentials are correctly formatted in Secrets
- Check that the service account has Sheet access
- Ensure the Sheet ID is correct in `utils.py`

### Module Import Errors
- Check `requirements.txt` has all dependencies
- Verify Python version compatibility (3.9+)

### Connection Timeout
- Check internet connectivity
- Verify Google API is enabled in GCP

## Local Testing

To test your cloud setup locally:

1. Create `.streamlit/secrets.toml` (same format as above)
2. Run: `streamlit run Clientes.py`
3. Streamlit automatically loads secrets from the file

## Costs

- **Streamlit Cloud Free Tier**: Always free for public apps
- **Google Sheets**: Free up to quotas
- **No additional charges** for basic usage

## Support

- Streamlit Docs: https://docs.streamlit.io/deploy/streamlit-cloud
- Google API Docs: https://developers.google.com/sheets/api

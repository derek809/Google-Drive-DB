core/Infrastructure/

import msal

# These come from the steps above
config = {
    "client_id": "YOUR_CLIENT_ID",
    "secret": "YOUR_CLIENT_SECRET",
    "authority": "https://login.microsoftonline.com/YOUR_TENANT_ID"
}

app = msal.ConfidentialClientApplication(
    config['client_id'], 
    authority=config['authority'],
    client_credential=config['secret']
)

# Request token for SharePoint access
token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
# Use token['access_token'] to call the SharePoint API
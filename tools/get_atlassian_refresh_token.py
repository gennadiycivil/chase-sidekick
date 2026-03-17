#!/usr/bin/env python3
"""Helper script to obtain an Atlassian OAuth2 refresh token.

This script guides you through the OAuth 2.0 (3LO) authorization code flow
to get a long-lived refresh token for JIRA and Confluence APIs.

Prerequisites:
1. Go to https://developer.atlassian.com/console/myapps/
2. Create an OAuth 2.0 (3LO) app
3. Under "Authorization", add callback URL: http://localhost:8901/callback
4. Under "Permissions", add JIRA API scopes:
   - read:jira-work
   - write:jira-work
   - read:jira-user
   And Confluence API scopes (if needed):
   - read:confluence-content.all
   - write:confluence-content
5. Note the Client ID and Secret from the "Settings" page
"""

import sys
import json
import urllib.request
import urllib.parse
import webbrowser
import http.server
import threading


# Scopes for JIRA + Confluence access
SCOPES = [
    "offline_access",       # Required for refresh tokens
    "read:jira-work",       # Read issues, projects, boards
    "write:jira-work",      # Create/edit issues, comments
    "read:jira-user",       # Read user profiles
    "read:confluence-content.all",  # Read Confluence pages
    "write:confluence-content",     # Write Confluence pages
]

CALLBACK_PORT = 8901
CALLBACK_PATH = "/callback"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback code."""

    auth_code = None
    error = None

    def do_GET(self):
        """Handle GET request from OAuth callback."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == CALLBACK_PATH:
            if "code" in params:
                _CallbackHandler.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authorization successful!</h2>"
                    b"<p>You can close this tab and return to the terminal.</p>"
                    b"</body></html>"
                )
            else:
                _CallbackHandler.error = params.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authorization failed</h2>"
                    b"<p>Check the terminal for details.</p>"
                    b"</body></html>"
                )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass


def get_authorization_code(client_id: str) -> str:
    """Open browser for authorization and capture code via local callback server."""
    auth_url = "https://auth.atlassian.com/authorize?" + urllib.parse.urlencode({
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": " ".join(SCOPES),
        "redirect_uri": REDIRECT_URI,
        "state": "sidekick_setup",
        "response_type": "code",
        "prompt": "consent",
    })

    # Start local server to capture callback
    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server.timeout = 120  # 2 minute timeout

    print("\n" + "=" * 80)
    print("STEP 1: Authorize the application")
    print("=" * 80)
    print("\nOpening your browser to authorize the application...")
    print(f"\nIf the browser doesn't open automatically, visit this URL:\n{auth_url}\n")

    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f"Could not open browser: {e}")

    print("Waiting for authorization callback...")

    # Handle requests until we get the code or timeout
    while _CallbackHandler.auth_code is None and _CallbackHandler.error is None:
        server.handle_request()

    server.server_close()

    if _CallbackHandler.error:
        raise ValueError(f"Authorization failed: {_CallbackHandler.error}")

    if not _CallbackHandler.auth_code:
        raise ValueError("No authorization code received (timed out)")

    return _CallbackHandler.auth_code


def exchange_code_for_tokens(client_id: str, client_secret: str, code: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    token_url = "https://auth.atlassian.com/oauth/token"

    data = json.dumps({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }).encode('utf-8')

    req = urllib.request.Request(token_url, data=data, method='POST')
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise ValueError(f"Failed to get tokens: {e.code} - {error_body}")


def get_accessible_resources(access_token: str) -> list:
    """Get list of Atlassian Cloud sites accessible with this token."""
    url = "https://api.atlassian.com/oauth/token/accessible-resources"

    req = urllib.request.Request(url, method='GET')
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise ValueError(f"Failed to get accessible resources: {e.code} - {error_body}")


def main():
    """Main function to guide user through OAuth flow."""
    print("=" * 80)
    print("Atlassian OAuth2 Refresh Token Generator")
    print("=" * 80)
    print("\nThis script will help you obtain a long-lived refresh token for")
    print("JIRA and Confluence. Refresh tokens auto-rotate, so you won't need")
    print("to manually renew API tokens anymore.")
    print("\nPrerequisites:")
    print("  1. OAuth 2.0 (3LO) app created at https://developer.atlassian.com/console/myapps/")
    print(f"  2. Callback URL configured: {REDIRECT_URI}")
    print("  3. JIRA API permissions added (read:jira-work, write:jira-work, read:jira-user)")
    print("  4. Client ID and Secret from Settings page")

    input("\nPress Enter to continue...")

    # Get credentials
    print("\n" + "=" * 80)
    print("Enter your Atlassian app credentials")
    print("=" * 80)

    client_id = input("\nClient ID: ").strip()
    if not client_id:
        print("Error: Client ID is required")
        sys.exit(1)

    client_secret = input("Client Secret: ").strip()
    if not client_secret:
        print("Error: Client Secret is required")
        sys.exit(1)

    try:
        # Get authorization code via browser callback
        code = get_authorization_code(client_id)

        print("\n" + "=" * 80)
        print("STEP 2: Exchange code for tokens")
        print("=" * 80)
        print("\nExchanging authorization code for tokens...")

        # Exchange for tokens
        tokens = exchange_code_for_tokens(client_id, client_secret, code)

        if "refresh_token" not in tokens:
            print("\nWARNING: No refresh token received!")
            print("Make sure 'offline_access' scope was included.")
            print("Try running this script again.")
            sys.exit(1)

        # Get cloud ID
        print("\n" + "=" * 80)
        print("STEP 3: Get your Atlassian Cloud site ID")
        print("=" * 80)
        print("\nFetching accessible Atlassian sites...")

        resources = get_accessible_resources(tokens["access_token"])

        if not resources:
            print("\nERROR: No accessible Atlassian sites found.")
            print("Make sure your app has the correct permissions.")
            sys.exit(1)

        # Let user choose if multiple sites
        if len(resources) == 1:
            cloud_id = resources[0]["id"]
            site_name = resources[0].get("name", resources[0].get("url", "Unknown"))
            print(f"\nFound site: {site_name}")
            print(f"Cloud ID: {cloud_id}")
        else:
            print(f"\nFound {len(resources)} accessible sites:")
            for i, r in enumerate(resources):
                name = r.get("name", r.get("url", "Unknown"))
                print(f"  [{i + 1}] {name} (ID: {r['id']})")

            choice = input(f"\nSelect site [1-{len(resources)}]: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(resources):
                    cloud_id = resources[idx]["id"]
                else:
                    print("Invalid selection")
                    sys.exit(1)
            except ValueError:
                print("Invalid selection")
                sys.exit(1)

        # Display results
        print("\n" + "=" * 80)
        print("SUCCESS! Got your tokens")
        print("=" * 80)

        print("\n" + "-" * 80)
        print("Add these to your .env file:")
        print("-" * 80)
        print(f"ATLASSIAN_CLIENT_ID={client_id}")
        print(f"ATLASSIAN_CLIENT_SECRET={client_secret}")
        print(f"ATLASSIAN_REFRESH_TOKEN={tokens['refresh_token']}")
        print(f"ATLASSIAN_CLOUD_ID={cloud_id}")

        print("\n" + "=" * 80)
        print("Next steps:")
        print("=" * 80)
        print("1. Copy the four lines above to your .env file")
        print("2. You can comment out ATLASSIAN_API_TOKEN (no longer needed)")
        print("3. Test with: python -m sidekick.clients.jira get-issue <any-issue-key>")
        print("\nNote: Refresh tokens rotate automatically. The client saves")
        print("new tokens to .env on each refresh, so they persist across sessions.")

        print("\nDone!\n")

    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

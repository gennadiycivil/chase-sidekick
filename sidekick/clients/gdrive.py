"""Google Drive API Client - search, list, and get file metadata."""

import sys
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional


MIME_TYPES = {
    "doc": "application/vnd.google-apps.document",
    "sheet": "application/vnd.google-apps.spreadsheet",
    "slide": "application/vnd.google-apps.presentation",
    "folder": "application/vnd.google-apps.folder",
    "pdf": "application/pdf",
    "form": "application/vnd.google-apps.form",
}


class GDriveClient:
    """Google Drive API v3 client using native Python stdlib."""

    BASE_URL = "https://www.googleapis.com/drive/v3"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, timeout: int = 30):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.timeout = timeout
        self.access_token = None
        self.api_call_count = 0

    def _refresh_access_token(self) -> str:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        encoded = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token", data=encoded, method="POST"
        )
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())["access_token"]
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            raise ValueError(f"Failed to refresh access token: {e.code} - {body}")

    def _get_access_token(self) -> str:
        if not self.access_token:
            self.access_token = self._refresh_access_token()
        return self.access_token

    def _request(self, endpoint: str, params: Optional[dict] = None, retry_auth: bool = True) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self.api_call_count += 1
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            if e.code == 401 and retry_auth:
                self.access_token = None
                return self._request(endpoint, params, retry_auth=False)
            if e.code == 404:
                raise ValueError(f"Not found: {endpoint}")
            elif e.code >= 500:
                raise RuntimeError(f"Server error {e.code}: {body}")
            else:
                raise ValueError(f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error: {e.reason}")

    def search(self, query: str, page_size: int = 20, page_token: Optional[str] = None,
               order_by: str = "modifiedTime desc") -> dict:
        """Search files using Drive query syntax.

        Args:
            query: Drive API query string (e.g. "name contains 'report'")
            page_size: Number of results per page (max 1000)
            page_token: Token for next page of results
            order_by: Sort order (default: most recently modified first)

        Returns:
            Dict with keys: files (list of file dicts), nextPageToken (optional)
        """
        params = {
            "q": query,
            "pageSize": page_size,
            "orderBy": order_by,
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,owners,webViewLink,parents)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        return self._request("/files", params)

    def search_by_name(self, name: str, mime_type: Optional[str] = None,
                       page_size: int = 20) -> dict:
        """Search files by name (contains match).

        Args:
            name: Text to search for in file names
            mime_type: Optional MIME type filter (use MIME_TYPES keys for shortcuts)
            page_size: Number of results
        """
        # Escape single quotes in the name
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name contains '{escaped}' and trashed = false"
        if mime_type:
            resolved = MIME_TYPES.get(mime_type, mime_type)
            q += f" and mimeType = '{resolved}'"
        return self.search(q, page_size=page_size)

    def search_fulltext(self, text: str, mime_type: Optional[str] = None,
                        page_size: int = 20) -> dict:
        """Full-text search across file contents.

        Args:
            text: Text to search for in file contents
            mime_type: Optional MIME type filter
            page_size: Number of results
        """
        escaped = text.replace("\\", "\\\\").replace("'", "\\'")
        q = f"fullText contains '{escaped}' and trashed = false"
        if mime_type:
            resolved = MIME_TYPES.get(mime_type, mime_type)
            q += f" and mimeType = '{resolved}'"
        return self.search(q, page_size=page_size)

    def search_owned_by_me(self, name: Optional[str] = None, mime_type: Optional[str] = None,
                           page_size: int = 20) -> dict:
        """Search files owned by the authenticated user.

        Args:
            name: Optional name filter
            mime_type: Optional MIME type filter
            page_size: Number of results
        """
        q = "'me' in owners and trashed = false"
        if name:
            escaped = name.replace("\\", "\\\\").replace("'", "\\'")
            q += f" and name contains '{escaped}'"
        if mime_type:
            resolved = MIME_TYPES.get(mime_type, mime_type)
            q += f" and mimeType = '{resolved}'"
        return self.search(q, page_size=page_size)

    def list_folder(self, folder_id: str, page_size: int = 50,
                    page_token: Optional[str] = None) -> dict:
        """List files in a specific folder.

        Args:
            folder_id: ID of the folder (use 'root' for root folder)
            page_size: Number of results per page
            page_token: Token for next page
        """
        q = f"'{folder_id}' in parents and trashed = false"
        return self.search(q, page_size=page_size, page_token=page_token)

    def get_file(self, file_id: str) -> dict:
        """Get metadata for a specific file.

        Args:
            file_id: Google Drive file ID

        Returns:
            Dict with file metadata
        """
        params = {
            "fields": "id,name,mimeType,modifiedTime,createdTime,owners,webViewLink,parents,size,description",
            "supportsAllDrives": "true",
        }
        return self._request(f"/files/{file_id}", params)

    def list_recent(self, page_size: int = 20, mime_type: Optional[str] = None) -> dict:
        """List recently modified files.

        Args:
            page_size: Number of results
            mime_type: Optional MIME type filter
        """
        q = "trashed = false"
        if mime_type:
            resolved = MIME_TYPES.get(mime_type, mime_type)
            q += f" and mimeType = '{resolved}'"
        return self.search(q, page_size=page_size, order_by="viewedByMeTime desc")


def _format_file(f: dict) -> str:
    """Format a file dict as a one-line summary."""
    name = f.get("name", "Untitled")
    mime = f.get("mimeType", "")
    modified = f.get("modifiedTime", "")[:10]
    link = f.get("webViewLink", "")
    # Shorten mime type for display
    short_mime = mime.replace("application/vnd.google-apps.", "g:").replace("application/", "")
    return f"{name}  [{short_mime}]  {modified}  {link}"


def main():
    """CLI interface for Google Drive client."""
    if len(sys.argv) < 2:
        print("Usage: python -m sidekick.clients.gdrive <command> [args]")
        print("\nCommands:")
        print("  search <query>              - Raw Drive API query")
        print("  find <name> [type]          - Search by file name (type: doc/sheet/slide/folder/pdf)")
        print("  fulltext <text> [type]      - Full-text content search")
        print("  mine [name] [type]          - Files owned by me")
        print("  recent [type]               - Recently viewed files")
        print("  ls <folder_id>              - List folder contents")
        print("  get <file_id>               - Get file metadata")
        sys.exit(1)

    try:
        from sidekick.config import get_google_config
        config = get_google_config()
    except (ImportError, ValueError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    client = GDriveClient(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        refresh_token=config["refresh_token"],
    )

    command = sys.argv[1]

    try:
        if command == "search":
            if len(sys.argv) < 3:
                print("Error: Missing query", file=sys.stderr)
                sys.exit(1)
            result = client.search(sys.argv[2])
            files = result.get("files", [])
            print(f"Found {len(files)} files:")
            for f in files:
                print(f"  {_format_file(f)}")

        elif command == "find":
            if len(sys.argv) < 3:
                print("Error: Missing name", file=sys.stderr)
                sys.exit(1)
            mime = sys.argv[3] if len(sys.argv) > 3 else None
            result = client.search_by_name(sys.argv[2], mime_type=mime)
            files = result.get("files", [])
            print(f"Found {len(files)} files:")
            for f in files:
                print(f"  {_format_file(f)}")

        elif command == "fulltext":
            if len(sys.argv) < 3:
                print("Error: Missing search text", file=sys.stderr)
                sys.exit(1)
            mime = sys.argv[3] if len(sys.argv) > 3 else None
            result = client.search_fulltext(sys.argv[2], mime_type=mime)
            files = result.get("files", [])
            print(f"Found {len(files)} files:")
            for f in files:
                print(f"  {_format_file(f)}")

        elif command == "mine":
            name = sys.argv[2] if len(sys.argv) > 2 else None
            mime = sys.argv[3] if len(sys.argv) > 3 else None
            result = client.search_owned_by_me(name=name, mime_type=mime)
            files = result.get("files", [])
            print(f"Found {len(files)} files:")
            for f in files:
                print(f"  {_format_file(f)}")

        elif command == "recent":
            mime = sys.argv[2] if len(sys.argv) > 2 else None
            result = client.list_recent(mime_type=mime)
            files = result.get("files", [])
            print(f"Found {len(files)} files:")
            for f in files:
                print(f"  {_format_file(f)}")

        elif command == "ls":
            if len(sys.argv) < 3:
                print("Error: Missing folder_id", file=sys.stderr)
                sys.exit(1)
            result = client.list_folder(sys.argv[2])
            files = result.get("files", [])
            print(f"Found {len(files)} items:")
            for f in files:
                print(f"  {_format_file(f)}")

        elif command == "get":
            if len(sys.argv) < 3:
                print("Error: Missing file_id", file=sys.stderr)
                sys.exit(1)
            f = client.get_file(sys.argv[2])
            print(f"Name: {f.get('name', 'Untitled')}")
            print(f"Type: {f.get('mimeType', 'unknown')}")
            print(f"Modified: {f.get('modifiedTime', 'unknown')}")
            print(f"Created: {f.get('createdTime', 'unknown')}")
            if f.get("owners"):
                print(f"Owner: {f['owners'][0].get('displayName', 'unknown')}")
            print(f"URL: {f.get('webViewLink', 'N/A')}")
            if f.get("size"):
                print(f"Size: {f['size']} bytes")

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            sys.exit(1)

    except (ValueError, RuntimeError, ConnectionError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

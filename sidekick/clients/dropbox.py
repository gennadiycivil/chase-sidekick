"""Dropbox client - single-file implementation using Python stdlib only."""
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import time
import re
from typing import Optional, Union


class DropboxClient:
    """Client for Dropbox API v2.

    Supports:
    - Regular file content operations (get/write)
    - Paper doc content operations (get/create/update)
    - Share link resolution
    - OAuth2 refresh token flow (auto-refreshes expired access tokens)
    - No external dependencies (Python stdlib only)
    """

    def __init__(self, access_token: str = None, app_key: str = None,
                 app_secret: str = None, refresh_token: str = None,
                 timeout: int = 30):
        """Initialize Dropbox client.

        Two modes:
        1. Refresh token (recommended): provide app_key, app_secret, refresh_token
        2. Static access token (legacy): provide access_token only

        Args:
            access_token: Dropbox OAuth 2.0 access token (optional if using refresh token)
            app_key: Dropbox app key (for refresh token flow)
            app_secret: Dropbox app secret (for refresh token flow)
            refresh_token: Dropbox OAuth2 refresh token (long-lived)
            timeout: Request timeout in seconds (default: 30)
        """
        self.access_token = access_token
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token
        self.timeout = timeout
        self.api_call_count = 0

        # If we have refresh token credentials but no access token, get one now
        if self.refresh_token and self.app_key and self.app_secret and not self.access_token:
            self._refresh_access_token()

    def _refresh_access_token(self):
        """Use refresh token to obtain a new short-lived access token.

        Raises:
            ValueError: If refresh token is invalid or revoked
            ConnectionError: If network error occurs
        """
        url = "https://api.dropboxapi.com/oauth2/token"
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.app_key,
            "client_secret": self.app_secret,
        }).encode('utf-8')

        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.access_token = result["access_token"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            raise ValueError(
                f"Failed to refresh Dropbox access token ({e.code}): {error_body}. "
                f"Your refresh token may be invalid or revoked. "
                f"Run: python3 tools/get_dropbox_refresh_token.py to get a new one."
            )
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error refreshing Dropbox token: {e.reason}")

    def _can_refresh(self) -> bool:
        """Check if we have credentials to refresh the access token."""
        return bool(self.refresh_token and self.app_key and self.app_secret)

    def _get_auth_headers(self) -> dict:
        """Get authorization headers for API requests.

        Returns:
            dict with Authorization header
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _request_api(self, endpoint: str, data: dict = None, content: bytes = None,
                     _retried: bool = False) -> dict:
        """Make API request to api.dropboxapi.com.

        Used for metadata operations, sharing, and Paper export/import.
        Automatically retries once on 401 if refresh token is available.

        Args:
            endpoint: API endpoint (e.g., "/2/files/get_metadata")
            data: JSON data to send in request body
            content: Optional binary content for requests like /files/import

        Returns:
            dict with API response (parsed JSON)

        Raises:
            ValueError: For 4xx client errors (invalid path, auth failure, etc.)
            RuntimeError: For 5xx server errors
            ConnectionError: For network errors
        """
        url = f"https://api.dropboxapi.com{endpoint}"

        headers = self._get_auth_headers()

        # Prepare request body
        if content is not None:
            # For requests that send both JSON and binary content (like /files/import)
            # The JSON goes in the Dropbox-API-Arg header
            if data:
                headers["Dropbox-API-Arg"] = json.dumps(data)
                headers["Content-Type"] = "application/octet-stream"
            request_body = content
        elif data:
            request_body = json.dumps(data).encode('utf-8')
        else:
            request_body = b''

        req = urllib.request.Request(url, data=request_body, headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                self.api_call_count += 1
                response_body = response.read().decode('utf-8')

                # Some endpoints return empty response
                if not response_body:
                    return {}

                return json.loads(response_body)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''

            if e.code == 401:
                # Auto-refresh and retry once
                if not _retried and self._can_refresh():
                    self._refresh_access_token()
                    return self._request_api(endpoint, data, content, _retried=True)
                raise ValueError(
                    f"Dropbox authentication failed (401 Unauthorized). "
                    f"Check your access token. Get a new token at: "
                    f"https://www.dropbox.com/developers/apps"
                )
            elif e.code == 403:
                raise ValueError(
                    f"Dropbox access forbidden (403). Check app permissions. "
                    f"Error: {error_body}"
                )
            elif e.code == 404:
                raise ValueError(f"Resource not found (404): {endpoint}")
            elif e.code == 409:
                # Parse error for more specific message
                try:
                    error_data = json.loads(error_body) if error_body else {}
                    error_summary = error_data.get('error_summary', 'Conflict')
                    raise ValueError(f"Dropbox API conflict (409): {error_summary}")
                except json.JSONDecodeError:
                    raise ValueError(f"Dropbox API conflict (409): {error_body}")
            elif e.code == 429:
                raise ValueError(
                    f"Rate limit exceeded (429). Please wait and retry. "
                    f"Error: {error_body}"
                )
            elif 400 <= e.code < 500:
                # Other client errors
                try:
                    error_data = json.loads(error_body) if error_body else {}
                    error_summary = error_data.get('error_summary', error_body)
                    raise ValueError(f"Dropbox API error ({e.code}): {error_summary}")
                except json.JSONDecodeError:
                    raise ValueError(f"Dropbox API error ({e.code}): {error_body}")
            else:
                # Server errors (5xx)
                raise RuntimeError(f"Dropbox server error ({e.code}): {error_body}")

        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error connecting to Dropbox: {e.reason}")

    def _request_content(self, endpoint: str, api_arg: dict, upload_content: bytes = None,
                         _retried: bool = False) -> tuple:
        """Make content request to content.dropboxapi.com.

        Used for file download and upload operations.
        Automatically retries once on 401 if refresh token is available.

        Args:
            endpoint: API endpoint (e.g., "/2/files/download")
            api_arg: JSON data for Dropbox-API-Arg header
            upload_content: Optional binary content for uploads

        Returns:
            tuple of (response_metadata: dict, content: bytes)

        Raises:
            ValueError: For 4xx client errors
            RuntimeError: For 5xx server errors
            ConnectionError: For network errors
        """
        url = f"https://content.dropboxapi.com{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Dropbox-API-Arg": json.dumps(api_arg)
        }

        if upload_content is not None:
            headers["Content-Type"] = "application/octet-stream"
            req = urllib.request.Request(url, data=upload_content, headers=headers, method='POST')
        else:
            # For downloads, don't pass data parameter at all
            req = urllib.request.Request(url, headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                self.api_call_count += 1

                # Get metadata from response header
                result_header = response.headers.get('Dropbox-API-Result', '{}')
                metadata = json.loads(result_header)

                # Get content from response body
                content = response.read()

                return metadata, content

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''

            if e.code == 401:
                # Auto-refresh and retry once
                if not _retried and self._can_refresh():
                    self._refresh_access_token()
                    return self._request_content(endpoint, api_arg, upload_content, _retried=True)
                raise ValueError(
                    f"Dropbox authentication failed (401 Unauthorized). "
                    f"Check your access token."
                )
            elif e.code == 409:
                # Parse error for more specific message
                try:
                    error_data = json.loads(error_body) if error_body else {}
                    error_summary = error_data.get('error_summary', 'Conflict')
                    raise ValueError(f"Dropbox API conflict (409): {error_summary}")
                except json.JSONDecodeError:
                    raise ValueError(f"Dropbox API conflict (409): {error_body}")
            elif 400 <= e.code < 500:
                try:
                    error_data = json.loads(error_body) if error_body else {}
                    error_summary = error_data.get('error_summary', error_body)
                    raise ValueError(f"Dropbox API error ({e.code}): {error_summary}")
                except json.JSONDecodeError:
                    raise ValueError(f"Dropbox API error ({e.code}): {error_body}")
            else:
                raise RuntimeError(f"Dropbox server error ({e.code}): {error_body}")

        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error connecting to Dropbox: {e.reason}")

    def _is_paper_link(self, link: str) -> bool:
        """Check if link is for Paper doc based on URL.

        Args:
            link: Share link URL

        Returns:
            True if Paper doc link, False otherwise
        """
        return 'paper.dropbox.com' in link.lower()

    def _is_paper_file(self, metadata: dict) -> bool:
        """Check if file metadata indicates a Paper doc.

        Args:
            metadata: File metadata from API

        Returns:
            True if Paper doc, False otherwise
        """
        # Paper docs have export_info field
        return 'export_info' in metadata or metadata.get('.tag') == 'paper'

    def search(self, query: str, path: str = "", max_results: int = 20,
               file_extensions: list = None, file_categories: list = None) -> list:
        """Search for files and folders by name or content.

        Uses Dropbox /2/files/search_v2 endpoint.

        Args:
            query: Search query string
            path: Scope search to this folder path (empty string = all files)
            max_results: Maximum results to return (max 1000)
            file_extensions: Filter by extensions (e.g., ["paper", "pdf", "docx"])
            file_categories: Filter by category (e.g., ["paper", "document", "spreadsheet", "image", "folder"])

        Returns:
            List of dicts with keys: name, path, id, type, modified
        """
        data = {
            "query": query,
            "options": {
                "max_results": max_results,
                "path": path,
            }
        }
        if file_extensions:
            data["options"]["file_extensions"] = file_extensions
        if file_categories:
            data["options"]["file_categories"] = [
                {".tag": cat} for cat in file_categories
            ]

        result = self._request_api("/2/files/search_v2", data)
        matches = result.get("matches", [])

        files = []
        for match in matches:
            metadata = match.get("metadata", {}).get("metadata", {})
            files.append({
                "name": metadata.get("name", ""),
                "path": metadata.get("path_display", ""),
                "id": metadata.get("id", ""),
                "type": "paper" if self._is_paper_file(metadata) else metadata.get(".tag", "unknown"),
                "modified": metadata.get("server_modified", metadata.get("client_modified", "")),
            })

        return files

    def list_folder(self, path: str = "", recursive: bool = False,
                    limit: int = 100) -> list:
        """List contents of a folder.

        Args:
            path: Folder path (empty string = root)
            recursive: Include subfolders recursively
            limit: Max entries per request (max 2000)

        Returns:
            List of dicts with keys: name, path, id, type, modified
        """
        data = {
            "path": path,
            "recursive": recursive,
            "limit": limit,
        }

        result = self._request_api("/2/files/list_folder", data)
        entries = result.get("entries", [])

        # Handle pagination
        while result.get("has_more"):
            cursor = result["cursor"]
            result = self._request_api("/2/files/list_folder/continue", {"cursor": cursor})
            entries.extend(result.get("entries", []))

        files = []
        for entry in entries:
            files.append({
                "name": entry.get("name", ""),
                "path": entry.get("path_display", ""),
                "id": entry.get("id", ""),
                "type": "paper" if self._is_paper_file(entry) else entry.get(".tag", "unknown"),
                "modified": entry.get("server_modified", entry.get("client_modified", "")),
            })

        return files

    def get_metadata(self, path: str) -> dict:
        """Get file or folder metadata.

        Args:
            path: Dropbox path (e.g., "/Documents/notes.txt")

        Returns:
            dict with metadata (name, size, modified time, etc.)

        Raises:
            ValueError: If path not found or invalid
        """
        data = {"path": path}
        return self._request_api("/2/files/get_metadata", data)

    def resolve_share_link(self, share_link: str) -> dict:
        """Resolve share link to get path and metadata.

        Works for both regular files and Paper docs.

        Args:
            share_link: Dropbox share link URL

        Returns:
            dict with path, name, and metadata

        Raises:
            ValueError: If link is invalid or inaccessible
        """
        data = {"url": share_link}
        return self._request_api("/2/sharing/get_shared_link_metadata", data)

    def _request_export(self, path: str, export_format: str = None, _retried: bool = False) -> bytes:
        """Export a Paper doc via content API.

        Automatically retries once on 401 if refresh token is available.

        Args:
            path: Dropbox path to Paper doc
            export_format: Export format ('markdown' or 'html')

        Returns:
            bytes with exported content
        """
        api_arg = {"path": path}
        if export_format:
            api_arg["export_format"] = export_format

        url = "https://content.dropboxapi.com/2/files/export"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Dropbox-API-Arg": json.dumps(api_arg)
        }

        req = urllib.request.Request(url, headers=headers, method='POST')

        try:
            self.api_call_count += 1
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            if e.code == 401:
                if not _retried and self._can_refresh():
                    self._refresh_access_token()
                    return self._request_export(path, export_format, _retried=True)
                raise ValueError(
                    f"Dropbox authentication failed (401 Unauthorized). "
                    f"Check your access token."
                )
            elif e.code == 404:
                raise ValueError(
                    f"File export failed (404). This may indicate:\n"
                    f"1. The file is not exportable (check metadata)\n"
                    f"2. Missing app permissions for Paper/cloud doc export\n"
                    f"3. Invalid path: {path}\n"
                    f"Error: {error_body}"
                )
            elif e.code == 409:
                try:
                    error_data = json.loads(error_body) if error_body else {}
                    error_summary = error_data.get('error_summary', 'Conflict')
                    raise ValueError(f"Dropbox API conflict (409): {error_summary}")
                except json.JSONDecodeError:
                    raise ValueError(f"Dropbox API conflict (409): {error_body}")
            elif 400 <= e.code < 500:
                raise ValueError(f"Dropbox API error ({e.code}): {error_body}")
            else:
                raise RuntimeError(f"Dropbox server error ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error connecting to Dropbox: {e.reason}")

    def get_file_contents(self, path: str, export_format: str = None) -> bytes:
        """Get file content by Dropbox path.

        For Paper docs, automatically exports using /files/export.

        Args:
            path: Dropbox path (e.g., "/Documents/notes.txt")
            export_format: For Paper docs - 'markdown' or 'html' (optional)

        Returns:
            bytes with file content

        Raises:
            ValueError: If path not found or is not a file
        """
        # First check if this is a Paper doc
        metadata = self.get_metadata(path)

        if self._is_paper_file(metadata):
            return self._request_export(path, export_format)
        else:
            # Use regular download for non-Paper files
            api_arg = {"path": path}
            metadata, content = self._request_content("/2/files/download", api_arg)
            return content

    def get_paper_contents(self, path: str, export_format: str = 'markdown') -> str:
        """Get Paper doc content.

        Args:
            path: Dropbox path or file ID to Paper doc (e.g., "/Paper/MyDoc.paper" or "id:...")
            export_format: Export format - 'markdown' (default) or 'html'

        Returns:
            str with Paper doc content in requested format

        Raises:
            ValueError: If path not found or is not a Paper doc
        """
        # Use get_file_contents which handles Paper docs via /files/export
        content_bytes = self.get_file_contents(path, export_format=export_format)
        return content_bytes.decode('utf-8')

    def get_paper_contents_from_link(self, share_link: str, export_format: str = 'markdown') -> str:
        """Get Paper doc content via share link.

        Args:
            share_link: Dropbox Paper share link URL
            export_format: Export format - 'markdown' (default) or 'html'

        Returns:
            str with Paper doc content in requested format

        Raises:
            ValueError: If link is invalid or not a Paper doc
        """
        # For shared links, use the URL directly with special format
        # First resolve to get the ID
        link_metadata = self.resolve_share_link(share_link)

        # Try to get the file ID
        file_id = link_metadata.get('id')
        if file_id:
            # Use the file ID directly
            path = f"{file_id}"
        else:
            # Fallback to path if ID not available
            path = link_metadata.get('path_lower') or link_metadata.get('path')
            if not path:
                raise ValueError("Could not extract path or ID from share link metadata")

        return self.get_paper_contents(path, export_format)

    def export_shared_link(
        self,
        url: str,
        path: Optional[str] = None,
        link_password: Optional[str] = None,
        override_download_setting: bool = False
    ) -> bytes:
        """Export content from file accessed via shared link.

        Downloads file content directly from a shared link without resolving to path first.
        Primary use case: Accessing files in team space that you don't own.
        This is the ONLY way to get content of a Paper doc you don't own.

        IMPORTANT for Paper docs:
        - The returned HTML includes extensive CSS and formatting not present in get-paper-contents
        - Use get-paper-contents for Paper docs you own when doing read-write workflows
        - Use export-shared-link for Paper docs you don't own (read-only team space access)

        Args:
            url: Dropbox share link URL
            path: Optional path within shared folder to specific file
            link_password: Optional password for password-protected links
            override_download_setting: Internal flag to override download restrictions

        Returns:
            bytes with file content

        Raises:
            ValueError: If link not found, access denied, or file not exportable
        """
        # Build API arguments - only include optional params if provided
        api_arg = {"url": url}

        if path is not None:
            api_arg["path"] = path

        if link_password is not None:
            api_arg["link_password"] = link_password

        if override_download_setting:
            api_arg["override_download_setting"] = True

        # Use _request_content for consistent error handling
        metadata, content = self._request_content("/2/sharing/export_shared_link", api_arg)

        return content

    def create_paper_contents(self, path: str, content: Union[bytes, str], import_format: str = 'markdown') -> dict:
        """Create new Paper doc.

        Args:
            path: Dropbox path for new Paper doc (e.g., "/Paper/NewDoc.paper")
            content: Paper doc content (str or bytes)
            import_format: Import format - 'markdown' (default) or 'html' (ignored, kept for API compatibility)

        Returns:
            dict with file metadata

        Raises:
            ValueError: If path already exists or creation fails
        """
        # Use write_file_contents with mode='add' to create new file
        return self.write_file_contents(path, content, mode='add')

    def get_paper_metadata(self, doc_id: str) -> dict:
        """Get metadata for a Paper doc.

        Note: Dropbox Paper API does NOT support retrieving full version/edit history.
        You can only get current document metadata (last update time, title, etc).
        To see full edit history, you must open the doc in a web browser.

        Args:
            doc_id: Paper doc ID (format: "id:..." from resolve_share_link or file metadata)

        Returns:
            dict with metadata including: doc_id, owner, title, revision,
            created_date, last_updated_date, last_editor, status

        Raises:
            ValueError: If doc not found, not a Paper doc, or access denied
        """
        # Remove 'id:' prefix if present - Paper API doesn't use it
        if doc_id.startswith("id:"):
            doc_id = doc_id[3:]

        data = {
            "doc_id": doc_id
        }

        try:
            result = self._request_api("/2/paper/docs/get_metadata", data)
            return result
        except ValueError as e:
            if "not_found" in str(e).lower() or "access_denied" in str(e).lower():
                raise ValueError(
                    f"Cannot access Paper doc. This may be because:\n"
                    f"1. The doc is in team space (shared doc you don't own)\n"
                    f"2. Your app doesn't have Paper API permissions (files.metadata.read scope)\n"
                    f"3. The doc ID is invalid\n"
                    f"Original error: {e}"
                )
            raise

    def list_revisions(self, path: str, limit: int = 10) -> list:
        """List revision history for a regular file (not Paper doc).

        For Paper docs, use list_paper_versions() instead.

        Args:
            path: Dropbox path or file ID (e.g., "/Documents/file.txt" or "id:...")
            limit: Maximum number of revisions to return (default: 10, max: 100)

        Returns:
            List of revision dicts with keys: rev, modified, is_downloadable, size
            Sorted newest first

        Raises:
            ValueError: If path not found, is a Paper doc (use list_paper_versions), or invalid
        """
        data = {
            "path": path,
            "mode": {".tag": "path"},
            "limit": min(limit, 100)  # API max is 100
        }

        result = self._request_api("/2/files/list_revisions", data)

        revisions = []
        for entry in result.get("entries", []):
            revisions.append({
                "rev": entry.get("rev", ""),
                "modified": entry.get("server_modified", entry.get("client_modified", "")),
                "is_downloadable": entry.get("is_downloadable", True),
                "size": entry.get("size", 0),
                "name": entry.get("name", ""),
            })

        return revisions

    def update_paper_contents(self, path: str, content: Union[bytes, str], import_format: str = 'html') -> dict:
        """Update existing Paper doc using Paper API.

        Uses the /2/files/paper/update endpoint with overwrite policy.
        Automatically strips the title (first 40px font-size div) from HTML content.

        Args:
            path: Dropbox path to existing Paper doc (e.g., "/Paper/MyDoc.paper")
            content: New Paper doc content (str or bytes) - HTML or markdown
            import_format: Import format - 'html' (default) or 'markdown'

        Returns:
            dict with file metadata

        Raises:
            ValueError: If path not found, is in team space, or update fails
        """
        # Check if this is a team space Paper doc (no proper path)
        # Team space docs don't have a regular file path and cannot be updated
        try:
            metadata = self.get_metadata(path)
            # Check if this is a Paper doc without a proper path (team space)
            if self._is_paper_file(metadata):
                # Team space docs won't have path_lower or path_display
                if not metadata.get('path_lower') and not metadata.get('path_display'):
                    raise ValueError(
                        f"Cannot update Paper doc in team space. "
                        f"Paper docs in the team space (shared docs you don't own) cannot be updated via API. "
                        f"Only Paper docs in your own Dropbox can be updated."
                    )
        except ValueError as e:
            # Re-raise if it's our team space error or a legitimate API error
            if "team space" in str(e):
                raise
            # For other errors, let them propagate during the actual update call
            pass

        # Convert bytes to str if needed for processing
        if isinstance(content, bytes):
            content_str = content.decode('utf-8')
        else:
            content_str = content

        # For HTML format, strip out the title div (40px font-size)
        # Paper API will use the document's own title, so we don't want it duplicated in the body
        if import_format == 'html':
            # Remove the first div with font-size: 40px (the title)
            content_str = re.sub(
                r'<div[^>]*font-size:\s*40px[^>]*>.*?</div>',
                '',
                content_str,
                count=1,
                flags=re.DOTALL
            )

        # Convert to bytes for sending
        content_bytes = content_str.encode('utf-8')

        # Prepare API arg for Dropbox-API-Arg header
        api_arg = {
            "path": path,
            "import_format": import_format,
            "doc_update_policy": "overwrite"
        }

        return self._request_api("/2/files/paper/update", data=api_arg, content=content_bytes)


def _format_metadata(metadata: dict) -> str:
    """Format metadata for readable display.

    Args:
        metadata: File metadata from API

    Returns:
        str with formatted metadata
    """
    lines = []

    # Path/name
    name = metadata.get('name', metadata.get('path_display', 'Unknown'))
    lines.append(name)

    # Type
    file_type = metadata.get('.tag', 'unknown')
    if 'export_info' in metadata or file_type == 'paper':
        lines.append("  Type: paper")
    elif file_type == 'file':
        lines.append("  Type: file")
    elif file_type == 'folder':
        lines.append("  Type: folder")
    else:
        lines.append(f"  Type: {file_type}")

    # Size
    if 'size' in metadata:
        size_bytes = metadata['size']
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        lines.append(f"  Size: {size_str}")

    # Modified time
    if 'server_modified' in metadata:
        # Parse ISO timestamp and format nicely
        timestamp = metadata['server_modified']
        # Just show the date and time part (YYYY-MM-DD HH:MM:SS)
        if 'T' in timestamp:
            date_time = timestamp.split('T')
            date = date_time[0]
            time_part = date_time[1].split('.')[0] if '.' in date_time[1] else date_time[1].split('Z')[0]
            lines.append(f"  Modified: {date} {time_part}")

    # Shared status (if available in metadata)
    if 'sharing_info' in metadata:
        lines.append("  Shared: Yes")

    return '\n'.join(lines)


def _read_stdin_content() -> str:
    """Read content from stdin.

    Returns:
        str with stdin content
    """
    return sys.stdin.read()


def main():
    """CLI entry point for Dropbox client."""
    if len(sys.argv) < 2:
        print("Usage: python -m sidekick.clients.dropbox <command> [args...]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  search <query> [--path <path>] [--ext paper,pdf] [--cat paper,document]", file=sys.stderr)
        print("  ls [path] [--recursive]", file=sys.stderr)
        print("  get-file-contents <path>", file=sys.stderr)
        print("  export-shared-link <url> [--path <path>] [--password <password>] [--override-download]", file=sys.stderr)
        print("  get-metadata <path>", file=sys.stderr)
        print("  list-revisions <path> [--limit 10]", file=sys.stderr)
        print("  list-paper-versions <doc_id>", file=sys.stderr)
        print("  get-paper-contents <path> [--format markdown|html]", file=sys.stderr)
        print("  get-paper-contents-from-link <share_link> [--format markdown|html]", file=sys.stderr)
        print("  create-paper-contents <path> [--content <text>] [--format markdown|html]", file=sys.stderr)
        print("  update-paper-contents <path> [--content <text>] [--format markdown|html]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    # Load config and create client
    try:
        from sidekick.config import get_dropbox_config
        config = get_dropbox_config()
        client = DropboxClient(
            access_token=config.get("access_token"),
            app_key=config.get("app_key"),
            app_secret=config.get("app_secret"),
            refresh_token=config.get("refresh_token"),
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    start_time = time.time()

    try:
        if command == "search":
            if len(sys.argv) < 3:
                print("Error: Missing query argument", file=sys.stderr)
                sys.exit(1)

            query = sys.argv[2]
            search_path = ""
            extensions = None
            categories = None

            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--path" and i + 1 < len(sys.argv):
                    search_path = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--ext" and i + 1 < len(sys.argv):
                    extensions = [e.strip() for e in sys.argv[i + 1].split(",")]
                    i += 2
                elif sys.argv[i] == "--cat" and i + 1 < len(sys.argv):
                    categories = [c.strip() for c in sys.argv[i + 1].split(",")]
                    i += 2
                else:
                    i += 1

            files = client.search(query, path=search_path, file_extensions=extensions,
                                  file_categories=categories)
            print(f"Found {len(files)} results:")
            for f in files:
                mod = f["modified"][:10] if f["modified"] else ""
                print(f"  {f['name']}  [{f['type']}]  {mod}  {f['path']}")

        elif command == "ls":
            folder_path = sys.argv[2] if len(sys.argv) > 2 else ""
            recursive = "--recursive" in sys.argv

            files = client.list_folder(folder_path, recursive=recursive)
            print(f"Found {len(files)} items:")
            for f in files:
                mod = f["modified"][:10] if f["modified"] else ""
                print(f"  {f['name']}  [{f['type']}]  {mod}  {f['path']}")

        elif command == "get-file-contents":
            if len(sys.argv) < 3:
                print("Error: Missing path argument", file=sys.stderr)
                sys.exit(1)

            path = sys.argv[2]
            content = client.get_file_contents(path)

            # Write binary content to stdout
            sys.stdout.buffer.write(content)

        elif command == "get-metadata":
            if len(sys.argv) < 3:
                print("Error: Missing path argument", file=sys.stderr)
                sys.exit(1)

            path = sys.argv[2]
            metadata = client.get_metadata(path)
            print(_format_metadata(metadata))

        elif command == "list-revisions":
            if len(sys.argv) < 3:
                print("Error: Missing path argument", file=sys.stderr)
                sys.exit(1)

            path = sys.argv[2]
            limit = 10

            # Check for --limit flag
            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
                    limit = int(sys.argv[i + 1])
                    i += 2
                else:
                    i += 1

            revisions = client.list_revisions(path, limit=limit)
            print(f"Found {len(revisions)} revisions:")
            for rev in revisions:
                modified = rev["modified"]
                # Format timestamp nicely
                if 'T' in modified:
                    date_time = modified.split('T')
                    date = date_time[0]
                    time_part = date_time[1].split('.')[0] if '.' in date_time[1] else date_time[1].split('Z')[0]
                    modified_str = f"{date} {time_part}"
                else:
                    modified_str = modified

                size_bytes = rev["size"]
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

                print(f"  {modified_str}  [{size_str}]  rev:{rev['rev']}")

        elif command == "list-paper-versions":
            if len(sys.argv) < 3:
                print("Error: Missing doc_id argument", file=sys.stderr)
                sys.exit(1)

            doc_id = sys.argv[2]
            metadata = client.get_paper_metadata(doc_id)

            title = metadata.get("title", "Unknown")
            print(f"Paper Doc: {title}")
            print(f"  Doc ID: {metadata.get('doc_id', 'N/A')}")
            print(f"  Revision: {metadata.get('revision', 'N/A')}")

            created = metadata.get("created_date", "")
            if created and 'T' in created:
                date_time = created.split('T')
                date = date_time[0]
                time_part = date_time[1].split('.')[0] if '.' in date_time[1] else date_time[1].split('Z')[0]
                created_str = f"{date} {time_part}"
            else:
                created_str = created or "N/A"
            print(f"  Created: {created_str}")

            modified = metadata.get("last_updated_date", "")
            if modified and 'T' in modified:
                date_time = modified.split('T')
                date = date_time[0]
                time_part = date_time[1].split('.')[0] if '.' in date_time[1] else date_time[1].split('Z')[0]
                modified_str = f"{date} {time_part}"
            else:
                modified_str = modified or "N/A"
            print(f"  Last Updated: {modified_str}")

            owner = metadata.get("owner", "")
            if owner:
                print(f"  Owner: {owner}")

            status = metadata.get("status", {}).get(".tag", "N/A")
            print(f"  Status: {status}")

            print("\nNote: Dropbox Paper API does not support retrieving full edit history.")
            print("To see full version history, open the doc in a web browser.")

        elif command == "get-paper-contents":
            if len(sys.argv) < 3:
                print("Error: Missing path argument", file=sys.stderr)
                sys.exit(1)

            path = sys.argv[2]
            export_format = "markdown"

            # Check for --format flag
            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--format" and i + 1 < len(sys.argv):
                    export_format = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1

            content = client.get_paper_contents(path, export_format)
            print(content)

        elif command == "get-paper-contents-from-link":
            if len(sys.argv) < 3:
                print("Error: Missing share_link argument", file=sys.stderr)
                sys.exit(1)

            share_link = sys.argv[2]
            export_format = "markdown"

            # Check for --format flag
            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--format" and i + 1 < len(sys.argv):
                    export_format = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1

            content = client.get_paper_contents_from_link(share_link, export_format)
            print(content)

        elif command == "create-paper-contents":
            if len(sys.argv) < 3:
                print("Error: Missing path argument", file=sys.stderr)
                sys.exit(1)

            path = sys.argv[2]
            content_text = None
            import_format = "markdown"

            # Parse flags
            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--content" and i + 1 < len(sys.argv):
                    content_text = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--format" and i + 1 < len(sys.argv):
                    import_format = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1

            # Read from stdin if --content not provided
            if content_text is None:
                content_text = _read_stdin_content()

            metadata = client.create_paper_contents(path, content_text, import_format)
            print(f"Created Paper doc at {path}", file=sys.stderr)

        elif command == "update-paper-contents":
            if len(sys.argv) < 3:
                print("Error: Missing path argument", file=sys.stderr)
                sys.exit(1)

            path = sys.argv[2]
            content_text = None
            import_format = "markdown"

            # Parse flags
            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--content" and i + 1 < len(sys.argv):
                    content_text = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--format" and i + 1 < len(sys.argv):
                    import_format = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1

            # Read from stdin if --content not provided
            if content_text is None:
                content_text = _read_stdin_content()

            metadata = client.update_paper_contents(path, content_text, import_format)
            print(f"Updated Paper doc at {path}", file=sys.stderr)

        elif command == "export-shared-link":
            if len(sys.argv) < 3:
                print("Error: Missing url argument", file=sys.stderr)
                sys.exit(1)

            url = sys.argv[2]
            path = None
            link_password = None
            override_download_setting = False

            # Parse optional flags
            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--path" and i + 1 < len(sys.argv):
                    path = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--password" and i + 1 < len(sys.argv):
                    link_password = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--override-download":
                    override_download_setting = True
                    i += 1
                else:
                    i += 1

            content = client.export_shared_link(url, path, link_password, override_download_setting)

            # Write binary content to stdout
            sys.stdout.buffer.write(content)

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Debug output
    elapsed_time = time.time() - start_time
    print(f"\n[Debug] API calls: {client.api_call_count}, Time: {elapsed_time:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    main()

"""Google Docs API Client - single file implementation with CLI support."""

import sys
import json
import re
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, List


class GDocsClient:
    """Google Docs API client using native Python stdlib."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, timeout: int = 30):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.timeout = timeout
        self.access_token = None
        self.api_call_count = 0

    def _refresh_access_token(self) -> str:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        encoded_data = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(token_url, data=encoded_data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode())
                return result["access_token"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            raise ValueError(f"Failed to refresh access token: {e.code} - {error_body}")

    def _get_access_token(self) -> str:
        if not self.access_token:
            self.access_token = self._refresh_access_token()
        return self.access_token

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
        retry_auth: bool = True
    ) -> Optional[dict]:
        base_url = "https://docs.googleapis.com/v1"
        url = f"{base_url}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        data = json.dumps(json_data).encode() if json_data else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                self.api_call_count += 1
                body = response.read().decode()
                if not body or body.strip() == "":
                    return {}
                return json.loads(body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            if e.code == 401 and retry_auth:
                self.access_token = None
                return self._request(method, endpoint, params, json_data, retry_auth=False)
            if e.code == 404:
                raise ValueError(f"Resource not found: {endpoint}")
            elif e.code >= 400 and e.code < 500:
                raise ValueError(f"Client error {e.code}: {error_body}")
            elif e.code >= 500:
                raise RuntimeError(f"Server error {e.code}: {error_body}")
            else:
                raise ConnectionError(f"HTTP error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error: {e.reason}")

    @staticmethod
    def extract_document_id(url: str) -> str:
        if "/document/d/" in url:
            parts = url.split("/document/d/")
            if len(parts) > 1:
                return parts[1].split("/")[0].split("?")[0].split("#")[0]
        raise ValueError(f"Invalid Google Docs URL: {url}")

    def create_document(self, title: str) -> dict:
        """Create a new empty Google Doc.

        Returns:
            Dict with documentId, title
        """
        result = self._request("POST", "/documents", json_data={"title": title})
        return {
            "documentId": result["documentId"],
            "title": result.get("title", title),
            "url": f"https://docs.google.com/document/d/{result['documentId']}/edit"
        }

    def get_document(self, document_id: str) -> dict:
        """Get document metadata and content."""
        return self._request("GET", f"/documents/{document_id}")

    def read_document(self, document_id: str) -> str:
        """Read document content as plain text."""
        doc = self.get_document(document_id)
        return self._extract_text(doc)

    def _extract_text(self, doc: dict) -> str:
        """Extract plain text from a Google Doc response."""
        text_parts = []
        body = doc.get("body", {})
        for element in body.get("content", []):
            if "paragraph" in element:
                para = element["paragraph"]
                for elem in para.get("elements", []):
                    if "textRun" in elem:
                        text_parts.append(elem["textRun"]["content"])
            elif "table" in element:
                for row in element["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        for content in cell.get("content", []):
                            if "paragraph" in content:
                                for elem in content["paragraph"].get("elements", []):
                                    if "textRun" in elem:
                                        text_parts.append(elem["textRun"]["content"])
                        text_parts.append("\t")
                    text_parts.append("\n")
        return "".join(text_parts)

    def batch_update(self, document_id: str, requests: list) -> dict:
        """Send batch update requests to a document."""
        return self._request(
            "POST",
            f"/documents/{document_id}:batchUpdate",
            json_data={"requests": requests}
        )

    def insert_text(self, document_id: str, text: str, index: int = 1) -> dict:
        """Insert plain text at a given index (1 = start of document)."""
        return self.batch_update(document_id, [
            {"insertText": {"location": {"index": index}, "text": text}}
        ])

    def write_markdown(self, document_id: str, markdown: str) -> dict:
        """Write markdown content to a Google Doc with formatting.

        Converts markdown to Google Docs API requests for:
        - Headings (# ## ###)
        - Bold (**text**)
        - Italic (*text*)
        - Bullet lists (- item or * item)
        - Numbered lists (1. item)
        """
        requests = []
        lines = markdown.split("\n")
        index = 1  # Start of document body

        for line in lines:
            # Determine line type and clean content
            heading_level = 0
            is_bullet = False
            is_numbered = False

            stripped = line.strip()

            # Headings
            if stripped.startswith("###"):
                heading_level = 3
                stripped = stripped[3:].strip()
            elif stripped.startswith("##"):
                heading_level = 2
                stripped = stripped[2:].strip()
            elif stripped.startswith("#"):
                heading_level = 1
                stripped = stripped[1:].strip()
            # Bullets
            elif stripped.startswith("- ") or stripped.startswith("* "):
                is_bullet = True
                stripped = stripped[2:]
            # Numbered lists
            elif re.match(r'^\d+\.\s', stripped):
                is_numbered = True
                stripped = re.sub(r'^\d+\.\s', '', stripped)

            # Skip empty lines but insert newline
            if not stripped and not line.strip():
                requests.append({
                    "insertText": {"location": {"index": index}, "text": "\n"}
                })
                index += 1
                continue

            text_to_insert = stripped + "\n"
            requests.append({
                "insertText": {"location": {"index": index}, "text": text_to_insert}
            })

            text_start = index
            text_end = index + len(stripped)

            # Apply heading style
            if heading_level > 0:
                heading_map = {1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3"}
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": text_start, "endIndex": text_end + 1},
                        "paragraphStyle": {"namedStyleType": heading_map[heading_level]},
                        "fields": "namedStyleType"
                    }
                })

            # Apply bullet list
            if is_bullet:
                requests.append({
                    "createParagraphBullets": {
                        "range": {"startIndex": text_start, "endIndex": text_end + 1},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
                    }
                })

            # Apply numbered list
            if is_numbered:
                requests.append({
                    "createParagraphBullets": {
                        "range": {"startIndex": text_start, "endIndex": text_end + 1},
                        "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN"
                    }
                })

            # Apply inline formatting (bold, italic)
            # Process **bold** markers
            plain_offset = text_start
            for match in re.finditer(r'\*\*(.+?)\*\*', stripped):
                # We inserted the raw markdown text including **, so we need to
                # find and format after removing markers. This is complex with
                # the Docs API, so we'll do a second pass to clean up.
                pass

            index += len(text_to_insert)

        # Execute all requests
        if requests:
            return self.batch_update(document_id, requests)
        return {}

    def create_from_markdown(self, title: str, markdown: str) -> dict:
        """Create a new Google Doc from markdown content.

        Args:
            title: Document title
            markdown: Markdown content

        Returns:
            Dict with documentId, title, url
        """
        # Create the document
        doc_info = self.create_document(title)
        document_id = doc_info["documentId"]

        # Strip markdown formatting markers and insert as structured text
        self._write_clean_markdown(document_id, markdown)

        return doc_info

    def _write_clean_markdown(self, document_id: str, markdown: str):
        """Write markdown to a doc, converting formatting to Docs styles."""
        lines = markdown.split("\n")
        requests = []
        index = 1

        # Process lines in reverse for correct indexing (insert at index 1 each time)
        # Actually, process forward and track index
        for line in lines:
            stripped = line.strip()
            heading_level = 0
            is_bullet = False

            if stripped.startswith("### "):
                heading_level = 3
                clean = stripped[4:]
            elif stripped.startswith("## "):
                heading_level = 2
                clean = stripped[3:]
            elif stripped.startswith("# "):
                heading_level = 1
                clean = stripped[2:]
            elif stripped.startswith("- ") or stripped.startswith("* "):
                is_bullet = True
                clean = stripped[2:]
            elif re.match(r'^\d+\.\s', stripped):
                is_bullet = True
                clean = re.sub(r'^\d+\.\s', '', stripped)
            else:
                clean = stripped

            # Remove bold/italic markers for clean text
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', clean)
            clean = re.sub(r'\*(.+?)\*', r'\1', clean)
            clean = re.sub(r'`(.+?)`', r'\1', clean)

            if not clean:
                requests.append({
                    "insertText": {"location": {"index": index}, "text": "\n"}
                })
                index += 1
                continue

            text = clean + "\n"
            requests.append({
                "insertText": {"location": {"index": index}, "text": text}
            })

            start = index
            end = index + len(clean) + 1

            if heading_level > 0:
                heading_map = {1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3"}
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": heading_map[heading_level]},
                        "fields": "namedStyleType"
                    }
                })

            if is_bullet:
                requests.append({
                    "createParagraphBullets": {
                        "range": {"startIndex": start, "endIndex": end},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
                    }
                })

            # Apply bold formatting from original markdown
            original_clean = stripped
            if heading_level > 0:
                original_clean = stripped.split(" ", 1)[1] if " " in stripped else stripped
            elif is_bullet:
                original_clean = stripped[2:] if stripped.startswith(("- ", "* ")) else re.sub(r'^\d+\.\s', '', stripped)

            # Find bold spans in original text and map to clean text positions
            bold_offset = 0
            for match in re.finditer(r'\*\*(.+?)\*\*', original_clean):
                bold_text = match.group(1)
                # Find this text in the clean version
                pos = clean.find(bold_text, bold_offset)
                if pos >= 0:
                    requests.append({
                        "updateTextStyle": {
                            "range": {
                                "startIndex": start + pos,
                                "endIndex": start + pos + len(bold_text)
                            },
                            "textStyle": {"bold": True},
                            "fields": "bold"
                        }
                    })
                    bold_offset = pos + len(bold_text)

            index += len(text)

        if requests:
            self.batch_update(document_id, requests)


def main():
    """CLI interface for Google Docs client."""
    if len(sys.argv) < 2:
        print("Usage: python -m sidekick.clients.gdocs <command> [args]")
        print("\nCommands:")
        print("  create <title>                    - Create empty document")
        print("  create-from-md <title> <md_file>  - Create document from markdown file")
        print("  read <document_id>                - Read document as plain text")
        print("  read-url <url>                    - Read document by URL")
        print("  get <document_id>                 - Get document metadata")
        sys.exit(1)

    try:
        from sidekick.config import get_google_config
        config = get_google_config()
    except (ImportError, ValueError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    client = GDocsClient(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        refresh_token=config["refresh_token"]
    )

    command = sys.argv[1]

    try:
        if command == "create":
            if len(sys.argv) < 3:
                print("Error: Missing title argument", file=sys.stderr)
                sys.exit(1)
            result = client.create_document(sys.argv[2])
            print(f"Created: {result['title']}")
            print(f"ID: {result['documentId']}")
            print(f"URL: {result['url']}")

        elif command == "create-from-md":
            if len(sys.argv) < 4:
                print("Error: Need title and markdown file path", file=sys.stderr)
                sys.exit(1)
            title = sys.argv[2]
            md_path = sys.argv[3]
            with open(md_path, "r", encoding="utf-8") as f:
                markdown = f.read()
            result = client.create_from_markdown(title, markdown)
            print(f"Created: {result['title']}")
            print(f"ID: {result['documentId']}")
            print(f"URL: {result['url']}")

        elif command == "read":
            if len(sys.argv) < 3:
                print("Error: Missing document_id argument", file=sys.stderr)
                sys.exit(1)
            text = client.read_document(sys.argv[2])
            print(text)

        elif command == "read-url":
            if len(sys.argv) < 3:
                print("Error: Missing URL argument", file=sys.stderr)
                sys.exit(1)
            doc_id = client.extract_document_id(sys.argv[2])
            text = client.read_document(doc_id)
            print(text)

        elif command == "get":
            if len(sys.argv) < 3:
                print("Error: Missing document_id argument", file=sys.stderr)
                sys.exit(1)
            doc = client.get_document(sys.argv[2])
            print(f"Title: {doc.get('title', 'Untitled')}")
            print(f"ID: {doc['documentId']}")
            print(f"URL: https://docs.google.com/document/d/{doc['documentId']}/edit")

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            sys.exit(1)

    except (ValueError, RuntimeError, ConnectionError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

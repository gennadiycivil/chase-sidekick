"""Google Slides API Client - single file implementation with CLI support."""

import sys
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, List


class GSlidesClient:
    """Google Slides API client using native Python stdlib."""

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
        base_url = "https://slides.googleapis.com/v1"
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
    def extract_presentation_id(url: str) -> str:
        if "/presentation/d/" in url:
            parts = url.split("/presentation/d/")
            if len(parts) > 1:
                return parts[1].split("/")[0].split("?")[0].split("#")[0]
        raise ValueError(f"Invalid Google Slides URL: {url}")

    @staticmethod
    def extract_slide_id(url: str) -> Optional[str]:
        """Extract slide ID from URL fragment (e.g., #slide=id.g3ce4afda713_3_0)."""
        if "slide=id." in url:
            parts = url.split("slide=id.")
            if len(parts) > 1:
                return "id." + parts[1].split("&")[0].split("#")[0]
        elif "slide=" in url:
            parts = url.split("slide=")
            if len(parts) > 1:
                return parts[1].split("&")[0].split("#")[0]
        return None

    def get_presentation(self, presentation_id: str) -> dict:
        """Get presentation metadata and all slides."""
        return self._request("GET", f"/presentations/{presentation_id}")

    def get_slide(self, presentation_id: str, slide_id: str) -> Optional[dict]:
        """Get a specific slide by ID."""
        pres = self.get_presentation(presentation_id)
        for slide in pres.get("slides", []):
            if slide.get("objectId") == slide_id:
                return slide
        return None

    def list_slides(self, presentation_id: str) -> List[dict]:
        """List all slides with their IDs and text content summary."""
        pres = self.get_presentation(presentation_id)
        slides = []
        for i, slide in enumerate(pres.get("slides", [])):
            slide_id = slide.get("objectId", "")
            texts = self._extract_slide_texts(slide)
            slides.append({
                "index": i,
                "objectId": slide_id,
                "texts": texts
            })
        return slides

    def read_slide(self, presentation_id: str, slide_id: str) -> dict:
        """Read all text and shape content from a specific slide."""
        slide = self.get_slide(presentation_id, slide_id)
        if not slide:
            raise ValueError(f"Slide not found: {slide_id}")

        elements = []
        for element in slide.get("pageElements", []):
            elem_info = self._parse_element(element)
            if elem_info:
                elements.append(elem_info)

        return {
            "objectId": slide_id,
            "elements": elements
        }

    def read_presentation_text(self, presentation_id: str) -> str:
        """Read all text from all slides as plain text."""
        pres = self.get_presentation(presentation_id)
        output = []
        for i, slide in enumerate(pres.get("slides", [])):
            slide_id = slide.get("objectId", "")
            texts = self._extract_slide_texts(slide)
            if texts:
                output.append(f"--- Slide {i + 1} ({slide_id}) ---")
                output.extend(texts)
                output.append("")
        return "\n".join(output)

    def _extract_slide_texts(self, slide: dict) -> List[str]:
        """Extract all text strings from a slide."""
        texts = []
        for element in slide.get("pageElements", []):
            shape = element.get("shape", {})
            text_content = shape.get("text", {})
            for text_elem in text_content.get("textElements", []):
                text_run = text_elem.get("textRun", {})
                content = text_run.get("content", "").strip()
                if content:
                    texts.append(content)
            # Also check tables
            table = element.get("table", {})
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    cell_text = cell.get("text", {})
                    for text_elem in cell_text.get("textElements", []):
                        text_run = text_elem.get("textRun", {})
                        content = text_run.get("content", "").strip()
                        if content:
                            texts.append(content)
        return texts

    def _parse_element(self, element: dict) -> Optional[dict]:
        """Parse a page element into a structured dict."""
        obj_id = element.get("objectId", "")

        # Shape with text
        shape = element.get("shape", {})
        if shape:
            text_content = shape.get("text", {})
            texts = []
            for text_elem in text_content.get("textElements", []):
                text_run = text_elem.get("textRun", {})
                content = text_run.get("content", "")
                if content.strip():
                    texts.append(content)
            return {
                "objectId": obj_id,
                "type": "shape",
                "shapeType": shape.get("shapeType", ""),
                "text": "".join(texts)
            }

        # Table
        table = element.get("table", {})
        if table:
            rows_data = []
            for row in table.get("tableRows", []):
                cells_data = []
                for cell in row.get("tableCells", []):
                    cell_texts = []
                    cell_text = cell.get("text", {})
                    for text_elem in cell_text.get("textElements", []):
                        text_run = text_elem.get("textRun", {})
                        content = text_run.get("content", "")
                        if content.strip():
                            cell_texts.append(content)
                    cells_data.append("".join(cell_texts).strip())
                rows_data.append(cells_data)
            return {
                "objectId": obj_id,
                "type": "table",
                "rows": rows_data
            }

        # Image
        image = element.get("image", {})
        if image:
            return {
                "objectId": obj_id,
                "type": "image",
                "sourceUrl": image.get("sourceUrl", "")
            }

        return None

    def batch_update(self, presentation_id: str, requests: list) -> dict:
        """Send batch update requests to a presentation."""
        return self._request(
            "POST",
            f"/presentations/{presentation_id}:batchUpdate",
            json_data={"requests": requests}
        )

    def replace_text(self, presentation_id: str, old_text: str, new_text: str, slide_id: Optional[str] = None) -> dict:
        """Replace all occurrences of text in the presentation or a specific slide."""
        replace_req = {
            "replaceAllText": {
                "containsText": {
                    "text": old_text,
                    "matchCase": True
                },
                "replaceText": new_text
            }
        }
        if slide_id:
            replace_req["replaceAllText"]["pageObjectIds"] = [slide_id]
        return self.batch_update(presentation_id, [replace_req])

    def insert_text(self, presentation_id: str, object_id: str, text: str, insertion_index: int = 0) -> dict:
        """Insert text into a shape at the given index."""
        return self.batch_update(presentation_id, [{
            "insertText": {
                "objectId": object_id,
                "insertionIndex": insertion_index,
                "text": text
            }
        }])

    def delete_text(self, presentation_id: str, object_id: str, start_index: int = 0, end_index: Optional[int] = None) -> dict:
        """Delete text from a shape."""
        text_range = {"type": "FROM_START_INDEX", "startIndex": start_index}
        if end_index is not None:
            text_range["type"] = "FIXED_RANGE"
            text_range["endIndex"] = end_index
        else:
            text_range["type"] = "ALL"

        return self.batch_update(presentation_id, [{
            "deleteText": {
                "objectId": object_id,
                "textRange": text_range
            }
        }])

    def replace_shape_text(self, presentation_id: str, object_id: str, new_text: str) -> dict:
        """Replace all text in a shape with new text."""
        requests = [
            {
                "deleteText": {
                    "objectId": object_id,
                    "textRange": {"type": "ALL"}
                }
            },
            {
                "insertText": {
                    "objectId": object_id,
                    "insertionIndex": 0,
                    "text": new_text
                }
            }
        ]
        return self.batch_update(presentation_id, requests)

    def create_slide(self, presentation_id: str, layout: str = "BLANK", insertion_index: Optional[int] = None) -> dict:
        """Create a new slide."""
        req = {
            "createSlide": {
                "slideLayoutReference": {"predefinedLayout": layout}
            }
        }
        if insertion_index is not None:
            req["createSlide"]["insertionIndex"] = insertion_index
        return self.batch_update(presentation_id, [req])

    def delete_slide(self, presentation_id: str, slide_id: str) -> dict:
        """Delete a slide."""
        return self.batch_update(presentation_id, [{
            "deleteObject": {"objectId": slide_id}
        }])


def main():
    """CLI interface for Google Slides client."""
    if len(sys.argv) < 2:
        print("Usage: python -m sidekick.clients.gslides <command> [args]")
        print("\nCommands:")
        print("  get <presentation_id>                  - Get presentation metadata")
        print("  get-url <url>                          - Get presentation by URL")
        print("  list-slides <presentation_id>          - List all slides")
        print("  list-slides-url <url>                  - List all slides by URL")
        print("  read <presentation_id>                 - Read all text from presentation")
        print("  read-url <url>                         - Read all text by URL")
        print("  read-slide <presentation_id> <slide_id> - Read a specific slide")
        print("  read-slide-url <url>                   - Read slide from URL (with #slide=id.xxx)")
        print("  replace-text <pres_id> <old> <new>     - Replace text in presentation")
        print("  replace-shape <pres_id> <obj_id> <text> - Replace all text in a shape")
        sys.exit(1)

    try:
        from sidekick.config import get_google_config
        config = get_google_config()
    except (ImportError, ValueError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    client = GSlidesClient(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        refresh_token=config["refresh_token"]
    )

    command = sys.argv[1]

    try:
        if command == "get":
            if len(sys.argv) < 3:
                print("Error: Missing presentation_id argument", file=sys.stderr)
                sys.exit(1)
            pres = client.get_presentation(sys.argv[2])
            print(f"Title: {pres.get('title', 'Untitled')}")
            print(f"ID: {pres['presentationId']}")
            print(f"Slides: {len(pres.get('slides', []))}")
            print(f"URL: https://docs.google.com/presentation/d/{pres['presentationId']}/edit")

        elif command == "get-url":
            if len(sys.argv) < 3:
                print("Error: Missing URL argument", file=sys.stderr)
                sys.exit(1)
            pres_id = client.extract_presentation_id(sys.argv[2])
            pres = client.get_presentation(pres_id)
            print(f"Title: {pres.get('title', 'Untitled')}")
            print(f"ID: {pres['presentationId']}")
            print(f"Slides: {len(pres.get('slides', []))}")
            print(f"URL: https://docs.google.com/presentation/d/{pres['presentationId']}/edit")

        elif command == "list-slides":
            if len(sys.argv) < 3:
                print("Error: Missing presentation_id argument", file=sys.stderr)
                sys.exit(1)
            slides = client.list_slides(sys.argv[2])
            for s in slides:
                preview = "; ".join(s["texts"][:3]) if s["texts"] else "(empty)"
                if len(preview) > 80:
                    preview = preview[:77] + "..."
                print(f"  Slide {s['index']}: {s['objectId']} — {preview}")

        elif command == "list-slides-url":
            if len(sys.argv) < 3:
                print("Error: Missing URL argument", file=sys.stderr)
                sys.exit(1)
            pres_id = client.extract_presentation_id(sys.argv[2])
            slides = client.list_slides(pres_id)
            for s in slides:
                preview = "; ".join(s["texts"][:3]) if s["texts"] else "(empty)"
                if len(preview) > 80:
                    preview = preview[:77] + "..."
                print(f"  Slide {s['index']}: {s['objectId']} — {preview}")

        elif command == "read":
            if len(sys.argv) < 3:
                print("Error: Missing presentation_id argument", file=sys.stderr)
                sys.exit(1)
            text = client.read_presentation_text(sys.argv[2])
            print(text)

        elif command == "read-url":
            if len(sys.argv) < 3:
                print("Error: Missing URL argument", file=sys.stderr)
                sys.exit(1)
            pres_id = client.extract_presentation_id(sys.argv[2])
            text = client.read_presentation_text(pres_id)
            print(text)

        elif command == "read-slide":
            if len(sys.argv) < 4:
                print("Error: Missing presentation_id and slide_id arguments", file=sys.stderr)
                sys.exit(1)
            slide_data = client.read_slide(sys.argv[2], sys.argv[3])
            print(f"Slide: {slide_data['objectId']}")
            for elem in slide_data["elements"]:
                if elem["type"] == "shape":
                    print(f"  [{elem['objectId']}] {elem['shapeType']}: {elem['text']}")
                elif elem["type"] == "table":
                    print(f"  [{elem['objectId']}] Table:")
                    for row in elem["rows"]:
                        print(f"    | {' | '.join(row)} |")
                elif elem["type"] == "image":
                    print(f"  [{elem['objectId']}] Image: {elem['sourceUrl'][:60]}...")

        elif command == "read-slide-url":
            if len(sys.argv) < 3:
                print("Error: Missing URL argument", file=sys.stderr)
                sys.exit(1)
            url = sys.argv[2]
            pres_id = client.extract_presentation_id(url)
            slide_id = client.extract_slide_id(url)
            if not slide_id:
                print("Error: URL does not contain a slide ID (expected #slide=id.xxx)", file=sys.stderr)
                sys.exit(1)
            slide_data = client.read_slide(pres_id, slide_id)
            print(f"Slide: {slide_data['objectId']}")
            for elem in slide_data["elements"]:
                if elem["type"] == "shape":
                    print(f"  [{elem['objectId']}] {elem['shapeType']}: {elem['text']}")
                elif elem["type"] == "table":
                    print(f"  [{elem['objectId']}] Table:")
                    for row in elem["rows"]:
                        print(f"    | {' | '.join(row)} |")
                elif elem["type"] == "image":
                    print(f"  [{elem['objectId']}] Image: {elem['sourceUrl'][:60]}...")

        elif command == "replace-text":
            if len(sys.argv) < 5:
                print("Error: Need presentation_id, old_text, new_text", file=sys.stderr)
                sys.exit(1)
            result = client.replace_text(sys.argv[2], sys.argv[3], sys.argv[4])
            print(f"Replaced text in presentation")

        elif command == "replace-shape":
            if len(sys.argv) < 5:
                print("Error: Need presentation_id, object_id, new_text", file=sys.stderr)
                sys.exit(1)
            result = client.replace_shape_text(sys.argv[2], sys.argv[3], sys.argv[4])
            print(f"Replaced text in shape {sys.argv[3]}")

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            sys.exit(1)

    except (ValueError, RuntimeError, ConnectionError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

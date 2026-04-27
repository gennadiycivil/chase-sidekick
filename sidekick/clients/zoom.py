"""Zoom Transcript Client - single file implementation with CLI support.

Discovers meetings via Google Calendar, fetches transcripts from Zoom API.
Supports date-range and person-based queries without manual meeting IDs.
"""

import sys
import json
import base64
import time
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional


class ZoomClient:
    """Zoom API client using Server-to-Server OAuth and native Python stdlib."""

    TOKEN_URL = "https://zoom.us/oauth/token"
    API_BASE = "https://api.zoom.us/v2"

    def __init__(
        self,
        account_id: str,
        client_id: str,
        client_secret: str,
        user_email: Optional[str] = None,
        timeout: int = 30
    ):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_email = user_email
        self.timeout = timeout
        self.access_token = None
        self.token_expires_at = 0
        self.api_call_count = 0

    # --- OAuth ---

    def _get_s2s_token(self) -> str:
        """Exchange S2S credentials for an access token."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        data = urllib.parse.urlencode({
            "grant_type": "account_credentials",
            "account_id": self.account_id
        }).encode()

        req = urllib.request.Request(self.TOKEN_URL, data=data, method="POST")
        req.add_header("Authorization", f"Basic {encoded}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode())
                self.access_token = result["access_token"]
                self.token_expires_at = time.time() + result.get("expires_in", 3600) - 60
                return self.access_token
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            raise ValueError(f"Zoom OAuth failed ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error during OAuth: {e.reason}")

    def _get_access_token(self) -> str:
        if not self.access_token or time.time() >= self.token_expires_at:
            self._get_s2s_token()
        return self.access_token

    # --- HTTP ---

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        retry_auth: bool = True
    ) -> dict:
        url = f"{self.API_BASE}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        req = urllib.request.Request(url, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self.api_call_count += 1
                body = resp.read().decode()
                if not body or body.strip() == "":
                    return {}
                return json.loads(body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""

            if e.code == 401 and retry_auth:
                self.access_token = None
                return self._request(method, endpoint, params, retry_auth=False)
            if e.code == 404:
                raise ValueError(f"Not found: {endpoint}")
            elif e.code == 400 and "does not contain scopes" in error_body:
                # Parse missing scopes from error for actionable message
                raise PermissionError(
                    f"Zoom app missing required scopes. "
                    f"Add them at https://marketplace.zoom.us/. "
                    f"Details: {error_body}"
                )
            elif 400 <= e.code < 500:
                raise ValueError(f"Client error {e.code}: {error_body}")
            else:
                raise RuntimeError(f"Server error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error: {e.reason}")

    def _request_raw(self, url: str, retry_auth: bool = True) -> str:
        """Fetch raw text content from a URL (for transcript downloads)."""
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self.api_call_count += 1
                return resp.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 401 and retry_auth:
                self.access_token = None
                return self._request_raw(url, retry_auth=False)
            error_body = e.read().decode() if e.fp else ""
            raise ValueError(f"Download failed ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error: {e.reason}")

    # --- API Methods ---

    def get_user(self, user_id: str = "me") -> dict:
        """Get user info. Use email address or 'me'."""
        return self._request("GET", f"/users/{user_id}")

    def list_recordings(
        self,
        user_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: int = 30
    ) -> list:
        """List cloud recordings for a user within a date range.

        Args:
            user_id: User ID or email (defaults to configured user_email)
            from_date: Start date YYYY-MM-DD (defaults to 30 days ago)
            to_date: End date YYYY-MM-DD (defaults to today)
            page_size: Results per page (max 300)

        Returns:
            List of meeting recording dicts
        """
        if not user_id:
            user_id = self.user_email or "me"

        today = datetime.now(timezone.utc)
        if not from_date:
            from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = today.strftime("%Y-%m-%d")

        # Zoom API limits date range to 1 month, so chunk if needed
        all_meetings = []
        chunk_from = datetime.strptime(from_date, "%Y-%m-%d")
        chunk_end = datetime.strptime(to_date, "%Y-%m-%d")

        while chunk_from < chunk_end:
            chunk_to = min(chunk_from + timedelta(days=30), chunk_end)
            params = {
                "from": chunk_from.strftime("%Y-%m-%d"),
                "to": chunk_to.strftime("%Y-%m-%d"),
                "page_size": page_size
            }

            next_token = ""
            while True:
                if next_token:
                    params["next_page_token"] = next_token

                result = self._request("GET", f"/users/{user_id}/recordings", params=params)
                meetings = result.get("meetings", [])
                all_meetings.extend(meetings)

                next_token = result.get("next_page_token", "")
                if not next_token:
                    break

            chunk_from = chunk_to

        return all_meetings

    def get_meeting_summary(self, meeting_uuid: str) -> Optional[dict]:
        """Get AI Companion meeting summary.

        Args:
            meeting_uuid: Meeting UUID (from past_meeting instances)

        Returns:
            Dict with summary_overview, summary_details, next_steps, etc.
            None if no summary available.
        """
        safe_id = urllib.parse.quote(urllib.parse.quote(str(meeting_uuid), safe=""), safe="")
        try:
            return self._request("GET", f"/meetings/{safe_id}/meeting_summary")
        except ValueError:
            return None

    def get_meeting_recordings(self, meeting_id: str) -> dict:
        """Get recordings for a specific meeting.

        Args:
            meeting_id: Meeting ID or UUID (double-encode if UUID contains /)

        Returns:
            Dict with meeting info and recording_files list
        """
        safe_id = urllib.parse.quote(urllib.parse.quote(str(meeting_id), safe=""), safe="")
        return self._request("GET", f"/meetings/{safe_id}/recordings")

    def get_transcript_url(self, meeting_id: str) -> Optional[str]:
        """Get the transcript download URL for a meeting.

        Returns:
            Transcript download URL, or None if no transcript available

        Raises:
            PermissionError: If app is missing required Zoom scopes
        """
        try:
            recordings = self.get_meeting_recordings(meeting_id)
        except PermissionError:
            raise  # Let scope errors bubble up
        except ValueError:
            return None

        for file in recordings.get("recording_files", []):
            if file.get("file_type") == "TRANSCRIPT":
                return file.get("download_url")
        return None

    def download_transcript(self, meeting_id: str) -> Optional[str]:
        """Download the VTT transcript for a meeting.

        Returns:
            Raw VTT transcript text, or None if no transcript
        """
        url = self.get_transcript_url(meeting_id)
        if not url:
            return None
        return self._request_raw(url)

    def get_past_meeting_instances(self, meeting_id: str) -> list:
        """Get past instances of a recurring meeting.

        Args:
            meeting_id: The meeting ID (numeric, not UUID)

        Returns:
            List of instance dicts with uuid, start_time
        """
        try:
            result = self._request("GET", f"/past_meetings/{meeting_id}/instances")
            return result.get("meetings", [])
        except ValueError:
            return []

    # --- Meeting Discovery via Google Calendar ---

    def find_meetings_from_calendar(
        self,
        from_date: str,
        to_date: str,
        attendee_filter: Optional[str] = None
    ) -> list:
        """Find Zoom meetings from Google Calendar events.

        Extracts meeting IDs from Zoom URLs in calendar events.

        Args:
            from_date: Start date YYYY-MM-DD
            to_date: End date YYYY-MM-DD
            attendee_filter: Optional name/email substring to filter by attendee

        Returns:
            List of dicts with: meeting_id, topic, start_time, attendees
        """
        from sidekick.config import get_google_config
        from sidekick.clients.gcalendar import GCalendarClient

        config = get_google_config()
        gcal = GCalendarClient(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            refresh_token=config["refresh_token"]
        )

        time_min = f"{from_date}T00:00:00Z"
        time_max = f"{to_date}T23:59:59Z"

        events = gcal.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=200
        )

        meetings = []
        for event in events:
            meeting_id = _extract_zoom_meeting_id(event)
            if not meeting_id:
                continue

            # Apply attendee filter
            attendees = [a.get("email", "") for a in event.get("attendees", [])]
            if attendee_filter:
                filter_lower = attendee_filter.lower()
                match = any(
                    filter_lower in a.lower()
                    for a in attendees
                )
                # Also check event summary
                summary = event.get("summary", "")
                if not match and filter_lower not in summary.lower():
                    continue

            start = event.get("start", {})
            start_time = start.get("dateTime", start.get("date", ""))

            meetings.append({
                "meeting_id": meeting_id,
                "topic": event.get("summary", "(No title)"),
                "start_time": start_time,
                "attendees": attendees,
                "event_id": event.get("id", "")
            })

        return meetings

    # --- High-Level: Fetch Transcripts ---

    def fetch_transcripts(
        self,
        from_date: str,
        to_date: str,
        attendee_filter: Optional[str] = None,
        use_calendar: bool = True
    ) -> list:
        """Fetch meeting transcripts for a date range.

        Two discovery modes:
        1. Calendar mode (default): Uses Google Calendar to find meetings,
           then fetches transcripts from Zoom. Better for filtering by attendee.
        2. Recordings mode: Lists recordings directly from Zoom API.

        Args:
            from_date: Start date YYYY-MM-DD
            to_date: End date YYYY-MM-DD
            attendee_filter: Optional name/email substring to filter meetings
            use_calendar: If True, discover meetings via calendar; else use Zoom recordings API

        Returns:
            List of dicts with: meeting_id, topic, start_time, transcript (parsed text)
        """
        results = []

        if use_calendar:
            meetings = self.find_meetings_from_calendar(from_date, to_date, attendee_filter)
            for m in meetings:
                mid = m["meeting_id"]
                vtt = self._try_download_transcript(mid)
                if vtt is None:
                    continue
                results.append({
                    "meeting_id": mid,
                    "topic": m["topic"],
                    "start_time": m["start_time"],
                    "transcript": parse_vtt_to_text(vtt)
                })
        else:
            recordings = self.list_recordings(from_date=from_date, to_date=to_date)
            for meeting in recordings:
                mid = str(meeting.get("id", ""))
                topic = meeting.get("topic", "(No topic)")
                start = meeting.get("start_time", "")

                # Apply attendee filter to topic if provided
                if attendee_filter:
                    if attendee_filter.lower() not in topic.lower():
                        continue

                # Check for transcript in recording files
                has_transcript = False
                for f in meeting.get("recording_files", []):
                    if f.get("file_type") == "TRANSCRIPT":
                        has_transcript = True
                        url = f.get("download_url")
                        if url:
                            try:
                                vtt = self._request_raw(url)
                                results.append({
                                    "meeting_id": mid,
                                    "topic": topic,
                                    "start_time": start,
                                    "transcript": parse_vtt_to_text(vtt)
                                })
                            except (ValueError, ConnectionError):
                                pass
                        break

        return results

    def _try_download_transcript(self, meeting_id: str) -> Optional[str]:
        """Try to download a transcript, returning None on failure.

        Handles recurring meetings by trying past instances.

        Raises:
            PermissionError: If app is missing required Zoom scopes
        """
        # Try direct download first
        try:
            vtt = self.download_transcript(meeting_id)
            if vtt:
                return vtt
        except PermissionError:
            raise  # Let scope errors bubble up
        except (ValueError, ConnectionError):
            pass

        # For recurring meetings, try past instances
        try:
            instances = self.get_past_meeting_instances(meeting_id)
            for instance in instances:
                uuid = instance.get("uuid", "")
                if uuid:
                    try:
                        vtt = self.download_transcript(uuid)
                        if vtt:
                            return vtt
                    except PermissionError:
                        raise
                    except (ValueError, ConnectionError):
                        continue
        except PermissionError:
            raise
        except (ValueError, ConnectionError):
            pass

        return None


# --- VTT Parsing ---

def parse_vtt_to_text(vtt_content: str) -> str:
    """Parse WebVTT transcript to clean 'Speaker: text' format.

    Strips timestamps and WEBVTT headers, deduplicates consecutive
    lines from the same speaker.

    Args:
        vtt_content: Raw VTT file content

    Returns:
        Clean transcript as "Speaker: text" lines
    """
    lines = vtt_content.strip().split("\n")
    output = []
    last_speaker = None
    timestamp_re = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")

    for line in lines:
        line = line.strip()
        # Skip empty lines, WEBVTT header, and timestamps
        if not line or line == "WEBVTT" or timestamp_re.match(line):
            continue
        # Skip numeric cue identifiers
        if line.isdigit():
            continue

        # Parse "Speaker Name: text" pattern
        match = re.match(r"^(.+?):\s*(.+)$", line)
        if match:
            speaker = match.group(1).strip()
            text = match.group(2).strip()
            if speaker == last_speaker:
                # Append to previous line
                if output:
                    output[-1] += " " + text
            else:
                output.append(f"{speaker}: {text}")
                last_speaker = speaker
        else:
            # Continuation line (no speaker prefix)
            if output:
                output[-1] += " " + line
            else:
                output.append(line)

    return "\n".join(output)


# --- Helpers ---

def _extract_zoom_meeting_id(event: dict) -> Optional[str]:
    """Extract Zoom meeting ID from a Google Calendar event.

    Checks conference data, location, and description for Zoom URLs.

    Returns:
        Meeting ID string, or None
    """
    # Check hangoutLink / conferenceData for Zoom
    conf_data = event.get("conferenceData", {})
    for entry_point in conf_data.get("entryPoints", []):
        uri = entry_point.get("uri", "")
        mid = _parse_zoom_url(uri)
        if mid:
            return mid

    # Check location field
    location = event.get("location", "")
    mid = _parse_zoom_url(location)
    if mid:
        return mid

    # Check description
    description = event.get("description", "")
    mid = _parse_zoom_url(description)
    if mid:
        return mid

    return None


def _parse_zoom_url(text: str) -> Optional[str]:
    """Extract meeting ID from a Zoom URL in text.

    Handles patterns like:
        https://dropbox.zoom.us/j/12345678901
        https://zoom.us/j/12345678901?pwd=abc
    """
    match = re.search(r"https?://[^/]*zoom\.us/j/(\d+)", text)
    if match:
        return match.group(1)
    return None


def _parse_date_range(text: str) -> tuple:
    """Parse natural language date range into (from_date, to_date) YYYY-MM-DD strings.

    Supports:
        "last week", "last 2 weeks", "last month", "last 3 months"
        "this week", "this month"
        "2024-01-01 to 2024-01-31"
        "yesterday", "today"
    """
    text = text.lower().strip()
    today = datetime.now(timezone.utc)

    if text == "today":
        d = today.strftime("%Y-%m-%d")
        return (d, d)
    if text == "yesterday":
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        return (d, d)
    if text == "this week":
        start = today - timedelta(days=today.weekday())
        return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    if text == "this month":
        start = today.replace(day=1)
        return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))

    # "last N weeks/months/days"
    match = re.match(r"last\s+(\d+)\s+(day|days|week|weeks|month|months)", text)
    if match:
        n = int(match.group(1))
        unit = match.group(2).rstrip("s")
        if unit == "day":
            delta = timedelta(days=n)
        elif unit == "week":
            delta = timedelta(weeks=n)
        elif unit == "month":
            delta = timedelta(days=n * 30)
        start = today - delta
        return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))

    # "last week" / "last month"
    if text == "last week":
        start = today - timedelta(weeks=1)
        return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    if text == "last month":
        start = today - timedelta(days=30)
        return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))

    # Explicit range: "YYYY-MM-DD to YYYY-MM-DD"
    range_match = re.match(r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", text)
    if range_match:
        return (range_match.group(1), range_match.group(2))

    # Single date
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if date_match:
        d = date_match.group(1)
        return (d, d)

    # Default: last 30 days
    start = today - timedelta(days=30)
    return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))


# --- CLI Formatting ---

def _format_meeting_oneline(meeting: dict) -> str:
    """Format meeting as one-line summary."""
    mid = meeting.get("meeting_id", meeting.get("id", ""))
    topic = meeting.get("topic", "(No topic)")
    start = meeting.get("start_time", "")
    if "T" in start:
        start = start[:16].replace("T", " ")
    return f"{mid}: {topic}  [{start}]"


def main():
    """CLI entry point for Zoom transcript client.

    Usage:
        python -m sidekick.clients.zoom auth-test
        python -m sidekick.clients.zoom list-recordings [from] [to]
        python -m sidekick.clients.zoom find-meetings [date-range] [--person NAME]
        python -m sidekick.clients.zoom transcript <meeting-id>
        python -m sidekick.clients.zoom transcripts [date-range] [--person NAME]
    """
    from sidekick.config import get_zoom_config

    if len(sys.argv) < 2:
        print("Usage: python -m sidekick.clients.zoom <command> [args...]")
        print("\nCommands:")
        print("  auth-test                            - Verify OAuth and user info")
        print("  list-recordings [from] [to]          - List recordings from Zoom API")
        print("  find-meetings [date-range]           - Find Zoom meetings via calendar")
        print("    --person NAME                        Filter by attendee name/email")
        print("  transcript <meeting-id>              - Download transcript for a meeting")
        print("  transcripts [date-range]             - Fetch all transcripts in range")
        print("    --person NAME                        Filter by attendee name/email")
        print("    --recordings                         Use Zoom recordings API instead of calendar")
        print("\nDate range examples:")
        print('  "last week", "last 2 weeks", "last month"')
        print('  "2024-01-01 to 2024-01-31"')
        sys.exit(1)

    try:
        start_time = time.time()

        config = get_zoom_config()
        client = ZoomClient(
            account_id=config["account_id"],
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            user_email=config["user_email"]
        )

        command = sys.argv[1]

        if command == "auth-test":
            user_id = config.get("user_email") or "me"
            user = client.get_user(user_id)
            print(f"User: {user.get('first_name', '')} {user.get('last_name', '')}")
            print(f"Email: {user.get('email', '')}")
            print(f"ID: {user.get('id', '')}")
            print(f"PMI: {user.get('pmi', '')}")
            print(f"Type: {user.get('type', '')}")
            print("OAuth token exchange: OK")

        elif command == "list-recordings":
            from_date = sys.argv[2] if len(sys.argv) > 2 else None
            to_date = sys.argv[3] if len(sys.argv) > 3 else None
            recordings = client.list_recordings(from_date=from_date, to_date=to_date)
            print(f"Found {len(recordings)} recordings:\n")
            for m in recordings:
                mid = m.get("id", "")
                topic = m.get("topic", "(No topic)")
                start = m.get("start_time", "")[:16].replace("T", " ")
                duration = m.get("duration", 0)
                files = m.get("recording_files", [])
                has_transcript = any(f.get("file_type") == "TRANSCRIPT" for f in files)
                tx_marker = " [transcript]" if has_transcript else ""
                print(f"  {mid}: {topic}  [{start}] ({duration}min){tx_marker}")

        elif command == "find-meetings":
            # Parse args
            person = None
            date_text = "last month"
            args = sys.argv[2:]
            i = 0
            date_parts = []
            while i < len(args):
                if args[i] == "--person" and i + 1 < len(args):
                    person = args[i + 1]
                    i += 2
                else:
                    date_parts.append(args[i])
                    i += 1
            if date_parts:
                date_text = " ".join(date_parts)

            from_date, to_date = _parse_date_range(date_text)
            print(f"Searching calendar for Zoom meetings: {from_date} to {to_date}")
            if person:
                print(f"Filtering by attendee: {person}")
            print()

            meetings = client.find_meetings_from_calendar(from_date, to_date, person)
            print(f"Found {len(meetings)} Zoom meetings:\n")
            for m in meetings:
                print(f"  {_format_meeting_oneline(m)}")

        elif command == "transcript":
            if len(sys.argv) < 3:
                print("Error: Missing meeting ID", file=sys.stderr)
                sys.exit(1)
            meeting_id = sys.argv[2]
            vtt = client.download_transcript(meeting_id)
            if vtt:
                print(parse_vtt_to_text(vtt))
            else:
                print(f"No transcript found for meeting {meeting_id}", file=sys.stderr)
                sys.exit(1)

        elif command == "transcripts":
            person = None
            use_recordings = False
            date_text = "last month"
            args = sys.argv[2:]
            i = 0
            date_parts = []
            while i < len(args):
                if args[i] == "--person" and i + 1 < len(args):
                    person = args[i + 1]
                    i += 2
                elif args[i] == "--recordings":
                    use_recordings = True
                    i += 1
                else:
                    date_parts.append(args[i])
                    i += 1
            if date_parts:
                date_text = " ".join(date_parts)

            from_date, to_date = _parse_date_range(date_text)
            mode = "Zoom recordings API" if use_recordings else "Google Calendar"
            print(f"Fetching transcripts: {from_date} to {to_date} (via {mode})")
            if person:
                print(f"Filtering by: {person}")
            print()

            results = client.fetch_transcripts(
                from_date, to_date,
                attendee_filter=person,
                use_calendar=not use_recordings
            )

            if not results:
                print("No transcripts found.")
            else:
                print(f"Found {len(results)} transcript(s):\n")
                for r in results:
                    print(f"--- {r['topic']} [{r['start_time'][:16].replace('T', ' ')}] ---")
                    # Print first 20 lines as preview
                    lines = r["transcript"].split("\n")
                    for line in lines[:20]:
                        print(f"  {line}")
                    if len(lines) > 20:
                        print(f"  ... ({len(lines) - 20} more lines)")
                    print()

        elif command == "summary":
            if len(sys.argv) < 3:
                print("Error: Missing meeting ID", file=sys.stderr)
                sys.exit(1)
            meeting_id = sys.argv[2]

            # Get the most recent instance UUID
            instances = client.get_past_meeting_instances(meeting_id)
            if not instances:
                print(f"No past instances for meeting {meeting_id}", file=sys.stderr)
                sys.exit(1)

            # Sort instances by start_time to get the most recent
            sorted_instances = sorted(instances, key=lambda x: x.get("start_time", ""))
            uuid = sorted_instances[-1]["uuid"]
            result = client.get_meeting_summary(uuid)
            if result:
                print(f"Meeting: {result.get('meeting_topic', '')}")
                print(f"Date: {result.get('meeting_start_time', '')[:16].replace('T', ' ')}")
                print(f"\nOverview:\n{result.get('summary_overview', 'N/A')}")
                details = result.get("summary_details", [])
                if details:
                    print(f"\nTopics ({len(details)}):")
                    for d in details:
                        print(f"  - {d.get('label', '')}")
                steps = result.get("next_steps", [])
                if steps:
                    print(f"\nNext Steps:")
                    for s in steps:
                        print(f"  - {s}")
            else:
                print(f"No summary found for meeting {meeting_id}", file=sys.stderr)
                sys.exit(1)

        elif command == "summaries":
            person = None
            date_text = "last week"
            args = sys.argv[2:]
            i = 0
            date_parts = []
            while i < len(args):
                if args[i] == "--person" and i + 1 < len(args):
                    person = args[i + 1]
                    i += 2
                else:
                    date_parts.append(args[i])
                    i += 1
            if date_parts:
                date_text = " ".join(date_parts)

            from_date, to_date = _parse_date_range(date_text)
            print(f"Fetching AI Companion summaries: {from_date} to {to_date}")
            if person:
                print(f"Filtering by: {person}")
            print()

            meetings = client.find_meetings_from_calendar(from_date, to_date, person)
            found = 0
            for m in meetings:
                mid = m["meeting_id"]
                instances = client.get_past_meeting_instances(mid)
                for inst in instances:
                    inst_date = inst.get("start_time", "")[:10]
                    if from_date <= inst_date <= to_date:
                        result = client.get_meeting_summary(inst["uuid"])
                        if result:
                            found += 1
                            overview = result.get("summary_overview", "")
                            details = result.get("summary_details", [])
                            topic_labels = [d.get("label", "") for d in details]
                            steps = result.get("next_steps", [])
                            print(f"--- {m['topic']} [{inst.get('start_time', '')[:16].replace('T', ' ')}] ---")
                            print(f"Overview: {overview[:200]}...")
                            if topic_labels:
                                print(f"Topics: {', '.join(topic_labels)}")
                            if steps:
                                print(f"Next steps: {len(steps)}")
                            print()
                        break  # Only latest matching instance per meeting

            if not found:
                print("No summaries found.")
            else:
                print(f"Found {found} meeting summaries.")

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            sys.exit(1)

        elapsed = time.time() - start_time
        print(f"\n[Debug] API calls: {client.api_call_count}, Time: {elapsed:.2f}s", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

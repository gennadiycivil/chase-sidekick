"""Watch Zoom assets for 1:1 meetings and add them to meeting docs.

The workflow is intentionally conservative:
- Calendar decides which meetings happened.
- A local watchlist decides which people are in scope.
- Zoom is polled for the matching meeting instance, not just the latest
  instance of a recurring meeting.
- Google Docs writes require --apply and read the document immediately before
  inserting a note.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Optional

from sidekick.clients.gcalendar import GCalendarClient
from sidekick.clients.gdocs import GDocsClient
from sidekick.clients.zoom import ZoomClient, _extract_zoom_meeting_id, parse_vtt_to_text
from sidekick.config import get_google_config, get_zoom_config


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WATCHLIST_PATH = REPO_ROOT / "memory" / "zoom_1on1_assets" / "watchlist.json"
DEFAULT_STATE_PATH = REPO_ROOT / "memory" / "zoom_1on1_assets" / "state.json"


def load_watchlist(path: Path = DEFAULT_WATCHLIST_PATH) -> dict:
    """Load and validate the local 1:1 watchlist."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing watchlist: {path}. Create it with self_email and people[]."
        )

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    self_email = data.get("self_email", "").strip().lower()
    people = data.get("people", [])
    if not self_email:
        raise ValueError(f"Watchlist {path} is missing self_email")
    if not isinstance(people, list) or not people:
        raise ValueError(f"Watchlist {path} must contain a non-empty people list")

    normalized_people = []
    seen = set()
    for person in people:
        email = person.get("email", "").strip().lower()
        name = person.get("name", "").strip()
        if not email or not name:
            raise ValueError("Each watched person needs name and email")
        if email in seen:
            raise ValueError(f"Duplicate watched email: {email}")
        seen.add(email)
        normalized = dict(person)
        normalized["email"] = email
        normalized["name"] = name
        normalized["summary_patterns"] = person.get("summary_patterns", [])
        normalized_people.append(normalized)

    return {
        "self_email": self_email,
        "people": normalized_people,
        "people_by_email": {p["email"]: p for p in normalized_people},
    }


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict:
    if not path.exists():
        return {"processed": {}}
    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    if "processed" not in state or not isinstance(state["processed"], dict):
        raise ValueError(f"Invalid state file: {path}")
    return state


def save_state(state: dict, path: Path = DEFAULT_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_path, path)


def parse_datetime(value: str) -> datetime:
    """Parse an RFC3339-ish timestamp into an aware datetime."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def event_start(event: dict) -> datetime:
    start = event.get("start", {})
    value = start.get("dateTime")
    if not value:
        raise ValueError(f"Event has no dateTime start: {event.get('id', '')}")
    return parse_datetime(value)


def event_end(event: dict) -> datetime:
    end = event.get("end", {})
    value = end.get("dateTime")
    if not value:
        raise ValueError(f"Event has no dateTime end: {event.get('id', '')}")
    return parse_datetime(value)


def find_allowed_counterpart(event: dict, watchlist: dict) -> Optional[dict]:
    """Return the watched non-self attendee when this is exactly a 1:1."""
    self_email = watchlist["self_email"]
    people_by_email = watchlist["people_by_email"]
    non_self = []
    for attendee in event.get("attendees", []):
        if attendee.get("resource"):
            continue
        email = attendee.get("email", "").strip().lower()
        if not email or email == self_email:
            continue
        non_self.append(email)

    if len(non_self) != 1:
        return None

    return people_by_email.get(non_self[0])


def _event_search_text(event: dict) -> str:
    parts = [
        event.get("summary", ""),
        event.get("description", ""),
        event.get("location", ""),
    ]
    for attachment in event.get("attachments", []) or []:
        parts.append(attachment.get("title", ""))
        parts.append(attachment.get("fileUrl", ""))
    return unescape(" ".join(p for p in parts if p))


def is_one_on_one_event(event: dict, person: dict) -> bool:
    """Return True if the event text or explicit watchlist pattern marks a 1:1."""
    text = _event_search_text(event)
    if re.search(r"\b1\s*[:/-]\s*1\b|\bone[- ]on[- ]one\b", text, re.IGNORECASE):
        return True

    summary = event.get("summary", "").strip().lower()
    for pattern in person.get("summary_patterns", []):
        pattern_lower = pattern.strip().lower()
        if pattern_lower and pattern_lower == summary:
            return True
    return False


def iter_eligible_events(events: list, watchlist: dict, now: datetime) -> list:
    """Filter calendar events down to ended, watched 1:1 Zoom meetings."""
    eligible = []
    for event in events:
        try:
            if event_end(event) > now:
                continue
        except ValueError:
            continue

        person = find_allowed_counterpart(event, watchlist)
        if not person:
            continue
        if not is_one_on_one_event(event, person):
            continue
        if not _extract_zoom_meeting_id(event):
            continue
        eligible.append((event, person))
    return eligible


def person_matches_filter(event: dict, person: dict, person_filter: Optional[str]) -> bool:
    if not person_filter:
        return True
    needle = person_filter.strip().lower()
    if not needle:
        return True
    haystacks = [
        person.get("name", ""),
        person.get("email", ""),
        event.get("summary", ""),
    ]
    return any(needle in value.lower() for value in haystacks)


def _google_doc_candidates_from_event(event: dict) -> list:
    candidates = []

    for attachment in event.get("attachments", []) or []:
        file_url = attachment.get("fileUrl", "")
        file_id = attachment.get("fileId", "")
        mime_type = attachment.get("mimeType", "")
        if mime_type == "application/vnd.google-apps.document" and file_id:
            candidates.append({
                "document_id": file_id,
                "tab_id": _extract_tab_id(file_url),
                "title": attachment.get("title", ""),
                "source": "attachment",
            })

    text = _event_search_text(event)
    for url in re.findall(r"https://docs\.google\.com/document/d/[^\s\"<>]+", text):
        doc_id, tab_id = GDocsClient.extract_document_id(url)
        candidates.append({
            "document_id": doc_id,
            "tab_id": tab_id,
            "title": "",
            "source": "event_text",
        })

    deduped = []
    seen = set()
    for candidate in candidates:
        key = (candidate["document_id"], candidate.get("tab_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _extract_tab_id(url: str) -> Optional[str]:
    if "?tab=" not in url:
        return None
    return url.split("?tab=", 1)[1].split("&", 1)[0].split("#", 1)[0]


def resolve_doc_target(event: dict, person: dict) -> dict:
    """Resolve the 1:1 Google Doc target from config or the event itself."""
    if person.get("doc_id"):
        return {
            "document_id": person["doc_id"],
            "tab_id": person.get("tab_id"),
            "title": person.get("doc_title", person["name"]),
            "source": "watchlist",
        }

    candidates = _google_doc_candidates_from_event(event)
    if not candidates:
        raise ValueError(
            f"No Google Doc found on event {event.get('id', '')} for {person['name']}"
        )
    if len(candidates) == 1:
        return candidates[0]

    person_name = person["name"].lower()
    preferred = [
        c for c in candidates
        if "1:1" in c.get("title", "").lower() or person_name in c.get("title", "").lower()
    ]
    if len(preferred) == 1:
        return preferred[0]

    ids = ", ".join(c["document_id"] for c in candidates)
    raise ValueError(
        f"Ambiguous Google Doc links on event {event.get('id', '')}: {ids}"
    )


def match_zoom_instance(
    zoom: ZoomClient,
    meeting_id: str,
    target_start: datetime,
    match_window_minutes: int,
) -> Optional[dict]:
    """Find the Zoom instance closest to the calendar event start."""
    instances = zoom.get_past_meeting_instances(meeting_id)
    if not instances:
        return None

    target_utc = target_start.astimezone(timezone.utc)
    matches = []
    for instance in instances:
        start_time = instance.get("start_time")
        if not start_time:
            continue
        instance_start = parse_datetime(start_time).astimezone(timezone.utc)
        delta_seconds = abs((instance_start - target_utc).total_seconds())
        matches.append((delta_seconds, instance))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0])
    closest_delta, closest = matches[0]
    if closest_delta > match_window_minutes * 60:
        return None
    return closest


def fetch_zoom_assets(
    zoom: ZoomClient,
    meeting_uuid: str,
    include_transcript: bool = False,
) -> dict:
    """Fetch Zoom assets for a specific meeting UUID."""
    summary = zoom.get_meeting_summary(meeting_uuid)
    transcript = None
    if include_transcript:
        try:
            raw_transcript = zoom.download_transcript(meeting_uuid)
            if raw_transcript:
                transcript = parse_vtt_to_text(raw_transcript)
        except (ValueError, ConnectionError):
            transcript = None
    return {"summary": summary, "transcript": transcript}


def assets_ready(assets: dict, require: str) -> bool:
    has_summary = bool(assets.get("summary"))
    has_transcript = bool(assets.get("transcript"))
    if require == "summary":
        return has_summary
    if require == "transcript":
        return has_transcript
    if require == "both":
        return has_summary and has_transcript
    if require == "any":
        return has_summary or has_transcript
    raise ValueError(f"Unknown require mode: {require}")


def build_marker(event: dict, meeting_uuid: str) -> str:
    return f"Zoom asset id: zoom-1on1-assets/{event.get('id', '')}/{meeting_uuid}"


def zoom_summary_doc_id(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"/doc/([A-Za-z0-9_-]+)", url)
    if not match:
        return None
    return match.group(1)


def format_display_date(dt: datetime) -> str:
    return dt.strftime("%B %-d, %Y")


def format_caption_date(dt: datetime) -> str:
    return dt.strftime("%m/%d/%Y")


def render_meeting_note(
    event: dict,
    person: dict,
    meeting_uuid: str,
    assets: dict,
    include_transcript: bool = False,
    note_style: str = "link",
) -> str:
    summary = assets.get("summary") or {}
    transcript = assets.get("transcript")
    summary_url = summary.get("summary_doc_url")

    if note_style == "link":
        if not summary_url:
            raise ValueError("Link note style requires a Zoom summary URL")
        return "\n".join([
            f"Summary for {format_caption_date(event_start(event))}: {summary_url}",
            "",
            "",
        ])
    if note_style != "full":
        raise ValueError(f"Unknown note style: {note_style}")

    lines = [
        "",
        "",
        f"Zoom assets - {format_display_date(event_start(event))}",
    ]

    if summary_url:
        lines.append(f"Summary: {summary_url}")

    overview = summary.get("summary_overview")
    if overview:
        lines.extend(["", "Overview:", overview.strip()])

    details = summary.get("summary_details") or []
    labels = [d.get("label", "").strip() for d in details if d.get("label", "").strip()]
    if labels:
        lines.extend(["", "Topics:"])
        lines.extend(f"- {label}" for label in labels)

    next_steps = [s.strip() for s in summary.get("next_steps", []) if str(s).strip()]
    if next_steps:
        lines.extend(["", "Next steps:"])
        lines.extend(f"- {step}" for step in next_steps)

    sources = []
    if summary:
        sources.append("Zoom AI summary")
    if transcript:
        sources.append("Zoom transcript")
    if sources:
        lines.extend(["", "Sources used:"])
        lines.extend(f"- {source}" for source in sources)

    if include_transcript and transcript:
        lines.extend(["", "Transcript:", transcript.strip()])

    lines.extend(["", build_marker(event, meeting_uuid), ""])
    return "\n".join(lines)


def _body_and_tab(doc: dict, tab_id: Optional[str]) -> tuple:
    if tab_id:
        for tab in doc.get("tabs", []):
            props = tab.get("tabProperties", {})
            if props.get("tabId") == tab_id:
                return tab.get("documentTab", {}).get("body", {}), tab_id
        raise ValueError(f"Tab '{tab_id}' not found in document")

    body = doc.get("body", {})
    if body.get("content"):
        return body, None

    tabs = doc.get("tabs", [])
    if tabs:
        first = tabs[0]
        first_tab_id = first.get("tabProperties", {}).get("tabId")
        return first.get("documentTab", {}).get("body", {}), first_tab_id

    raise ValueError("Document has no writable body")


def _paragraph_text(paragraph: dict) -> str:
    parts = []
    for element in paragraph.get("elements", []):
        if "dateElement" in element:
            props = element["dateElement"].get("dateElementProperties", {})
            parts.append(props.get("displayText", ""))
        elif "textRun" in element:
            parts.append(element["textRun"].get("content", ""))
    return "".join(parts)


_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _date_key(text: str) -> Optional[tuple]:
    normalized = re.sub(r"[,:\n]+", " ", text.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    word_match = re.search(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})\b", normalized)
    if word_match:
        month = _MONTHS.get(word_match.group(1))
        if not month:
            return None
        return (int(word_match.group(3)), month, int(word_match.group(2)))

    numeric_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", normalized)
    if not numeric_match:
        return None
    month = int(numeric_match.group(1))
    year = int(numeric_match.group(3))
    if year < 100:
        year += 2000
    if not month:
        return None
    return (year, month, int(numeric_match.group(2)))


def _insertion_index_after_date(body: dict, display_date: str) -> int:
    target_key = _date_key(display_date)
    for element in body.get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph).strip()
        if text == display_date or text.endswith(f" {display_date}"):
            return element["endIndex"]
        if target_key and _date_key(text) == target_key:
            return element["endIndex"]
    raise ValueError(f"Could not find meeting date heading: {display_date}")


def verify_note_present(
    gdocs: GDocsClient,
    document_id: str,
    tab_id: Optional[str],
    marker: str,
    summary_url: Optional[str] = None,
) -> bool:
    """Verify note presence in the same tab/body where it should be visible."""
    summary_doc_id = zoom_summary_doc_id(summary_url)
    if tab_id:
        current_text = gdocs.read_document(document_id, tab_id=tab_id)
        return marker in current_text or bool(summary_doc_id and summary_doc_id in current_text)

    doc = gdocs.get_document(document_id, include_tabs=True)
    body, resolved_tab_id = _body_and_tab(doc, None)
    if resolved_tab_id:
        current_text = gdocs.read_document(document_id, tab_id=resolved_tab_id)
    else:
        current_text = "".join(gdocs._extract_content_elements(body.get("content", [])))
    return marker in current_text or bool(summary_doc_id and summary_doc_id in current_text)


def append_note_to_doc(
    gdocs: GDocsClient,
    document_id: str,
    tab_id: Optional[str],
    note: str,
    marker: str,
    summary_url: Optional[str] = None,
    insert_after_date: Optional[str] = None,
) -> str:
    """Append a note after reading the latest document state."""
    current_text = gdocs.read_document(document_id, tab_id=tab_id)
    if marker in current_text:
        return "already-present"
    summary_doc_id = zoom_summary_doc_id(summary_url)
    if summary_doc_id and summary_doc_id in current_text:
        return "already-present"

    doc = gdocs.get_document(document_id, include_tabs=True)
    body, resolved_tab_id = _body_and_tab(doc, tab_id)
    content = body.get("content", [])
    if not content:
        raise ValueError(f"Document {document_id} has empty body content")

    if insert_after_date:
        index = _insertion_index_after_date(body, insert_after_date)
    else:
        end_index = content[-1].get("endIndex")
        if not end_index:
            raise ValueError(f"Document {document_id} has no end index")
        index = max(1, end_index - 1)

    location = {"index": index}
    if resolved_tab_id:
        location["tabId"] = resolved_tab_id

    requests = [{
        "insertText": {
            "location": location,
            "text": note,
        }
    }]
    inserted_end = index + len(note)
    requests.extend([
        {
            "deleteParagraphBullets": {
                "range": {
                    **({"tabId": resolved_tab_id} if resolved_tab_id else {}),
                    "startIndex": index,
                    "endIndex": inserted_end,
                }
            }
        },
        {
            "updateParagraphStyle": {
                "range": {
                    **({"tabId": resolved_tab_id} if resolved_tab_id else {}),
                    "startIndex": index,
                    "endIndex": inserted_end,
                },
                "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                "fields": "namedStyleType",
            }
        },
    ])
    if summary_url and summary_url in note:
        link_start = index + note.index(summary_url)
        requests.append({
            "updateTextStyle": {
                "range": {
                    **({"tabId": resolved_tab_id} if resolved_tab_id else {}),
                    "startIndex": link_start,
                    "endIndex": link_start + len(summary_url),
                },
                "textStyle": {"link": {"url": summary_url}},
                "fields": "link",
            }
        })

    gdocs.batch_update(document_id, requests)
    if not verify_note_present(
        gdocs,
        document_id,
        resolved_tab_id,
        marker,
        summary_url=summary_url,
    ):
        raise RuntimeError(f"Inserted note but could not verify it in document {document_id}")
    return "inserted"


def note_already_present(
    gdocs: GDocsClient,
    document_id: str,
    tab_id: Optional[str],
    marker: str,
    summary_url: Optional[str] = None,
) -> bool:
    current_text = gdocs.read_document(document_id, tab_id=tab_id)
    if marker in current_text:
        return True
    summary_doc_id = zoom_summary_doc_id(summary_url)
    return bool(summary_doc_id and summary_doc_id in current_text)


def _clients() -> tuple:
    google_config = get_google_config()
    zoom_config = get_zoom_config()
    gcal = GCalendarClient(
        client_id=google_config["client_id"],
        client_secret=google_config["client_secret"],
        refresh_token=google_config["refresh_token"],
    )
    gdocs = GDocsClient(
        client_id=google_config["client_id"],
        client_secret=google_config["client_secret"],
        refresh_token=google_config["refresh_token"],
    )
    zoom = ZoomClient(
        account_id=zoom_config["account_id"],
        client_id=zoom_config["client_id"],
        client_secret=zoom_config["client_secret"],
        user_email=zoom_config.get("user_email"),
    )
    return gcal, gdocs, zoom


def _event_status_key(event: dict, meeting_uuid: str) -> str:
    return f"{event.get('id', '')}:{meeting_uuid}"


def process_event(
    event: dict,
    person: dict,
    zoom: ZoomClient,
    gdocs: GDocsClient,
    state: dict,
    apply: bool,
    require: str,
    include_transcript: bool,
    match_window_minutes: int,
    note_style: str,
    check_docs: bool,
) -> dict:
    meeting_id = _extract_zoom_meeting_id(event)
    if not meeting_id:
        return {"status": "skipped", "reason": "no Zoom meeting ID", "event": event}

    instance = match_zoom_instance(
        zoom,
        meeting_id,
        event_start(event),
        match_window_minutes=match_window_minutes,
    )
    if not instance:
        return {"status": "pending", "reason": "no matching Zoom instance", "event": event}

    meeting_uuid = instance["uuid"]
    status_key = _event_status_key(event, meeting_uuid)
    if status_key in state.get("processed", {}):
        return {"status": "skipped", "reason": "already processed", "event": event}

    assets = fetch_zoom_assets(zoom, meeting_uuid, include_transcript=include_transcript)
    if not assets_ready(assets, require=require):
        return {
            "status": "pending",
            "reason": f"required Zoom asset not ready ({require})",
            "event": event,
            "meeting_uuid": meeting_uuid,
        }

    doc_target = resolve_doc_target(event, person)
    marker = build_marker(event, meeting_uuid)
    summary_url = (assets.get("summary") or {}).get("summary_doc_url")
    if note_style == "link" and not summary_url:
        return {
            "status": "pending",
            "reason": "Zoom summary has no summary_doc_url",
            "event": event,
            "person": person,
            "meeting_uuid": meeting_uuid,
            "doc_target": doc_target,
            "summary_url": summary_url,
            "marker": marker,
        }

    note = render_meeting_note(
        event,
        person,
        meeting_uuid,
        assets,
        include_transcript=include_transcript,
        note_style=note_style,
    )

    result = {
        "status": "ready",
        "event": event,
        "person": person,
        "meeting_uuid": meeting_uuid,
        "doc_target": doc_target,
        "summary_url": summary_url,
        "marker": marker,
    }

    if not apply and check_docs:
        if note_already_present(
            gdocs,
            doc_target["document_id"],
            doc_target.get("tab_id"),
            marker,
            summary_url=summary_url,
        ):
            result["status"] = "already-present"
        else:
            result["status"] = "missing-summary"

    if apply:
        write_status = append_note_to_doc(
            gdocs,
            doc_target["document_id"],
            doc_target.get("tab_id"),
            note,
            marker,
            summary_url=summary_url,
            insert_after_date=format_display_date(event_start(event)),
        )
        state["processed"][status_key] = {
            "event_id": event.get("id", ""),
            "meeting_uuid": meeting_uuid,
            "document_id": doc_target["document_id"],
            "tab_id": doc_target.get("tab_id"),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "write_status": write_status,
        }
        result["status"] = write_status

    return result


def scan_events(
    lookback_hours: int,
    watchlist_path: Path,
    state_path: Path,
    apply: bool,
    require: str,
    include_transcript: bool,
    match_window_minutes: int,
    max_results: int,
    note_style: str,
    check_docs: bool,
    person_filter: Optional[str],
) -> list:
    watchlist = load_watchlist(watchlist_path)
    state = load_state(state_path)
    gcal, gdocs, zoom = _clients()

    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(hours=lookback_hours)).isoformat()
    time_max = now.isoformat()
    events = gcal.list_events(
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
    )

    eligible = iter_eligible_events(events, watchlist, now=now)
    filtered = [
        (event, person)
        for event, person in eligible
        if person_matches_filter(event, person, person_filter)
    ]

    results = [
        process_event(
            event,
            person,
            zoom,
            gdocs,
            state,
            apply=apply,
            require=require,
            include_transcript=include_transcript,
            match_window_minutes=match_window_minutes,
            note_style=note_style,
            check_docs=check_docs,
        )
        for event, person in filtered
    ]

    if apply:
        save_state(state, state_path)
    return results


def process_single_event(
    event_id: str,
    watchlist_path: Path,
    state_path: Path,
    apply: bool,
    require: str,
    include_transcript: bool,
    match_window_minutes: int,
    note_style: str,
    check_docs: bool,
) -> dict:
    watchlist = load_watchlist(watchlist_path)
    state = load_state(state_path)
    gcal, gdocs, zoom = _clients()
    event = gcal.get_event(event_id)
    person = find_allowed_counterpart(event, watchlist)
    if not person:
        raise ValueError(f"Event {event_id} is not a watched 1:1")
    if not is_one_on_one_event(event, person):
        raise ValueError(f"Event {event_id} is not marked as a 1:1")

    result = process_event(
        event,
        person,
        zoom,
        gdocs,
        state,
        apply=apply,
        require=require,
        include_transcript=include_transcript,
        match_window_minutes=match_window_minutes,
        note_style=note_style,
        check_docs=check_docs,
    )
    if apply:
        save_state(state, state_path)
    return result


def print_results(results: list) -> None:
    if not results:
        print("No eligible watched 1:1 Zoom meetings found.")
        return

    for result in results:
        event = result.get("event", {})
        summary = event.get("summary", "(No title)")
        status = result.get("status")
        reason = result.get("reason")
        if reason:
            print(f"{status}: {summary} - {reason}")
            continue

        doc = result.get("doc_target", {})
        doc_id = doc.get("document_id", "")
        summary_url = result.get("summary_url") or "(no summary URL)"
        print(f"{status}: {summary}")
        print(f"  doc: https://docs.google.com/document/d/{doc_id}/edit")
        print(f"  summary: {summary_url}")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST_PATH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--apply", action="store_true", help="Write notes to Google Docs")
    parser.add_argument(
        "--require",
        choices=["summary", "transcript", "both", "any"],
        default="summary",
        help="Zoom asset readiness requirement",
    )
    parser.add_argument(
        "--include-transcript",
        action="store_true",
        help="Include parsed transcript text in the inserted note when available",
    )
    parser.add_argument("--match-window-minutes", type=int, default=120)
    parser.add_argument(
        "--note-style",
        choices=["link", "full"],
        default="link",
        help="Use link for the normal dated Summary link; full includes overview, topics, and next steps",
    )
    parser.add_argument(
        "--no-check-docs",
        action="store_true",
        help="Skip document duplicate checks during dry-runs",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Watch Zoom assets for watched 1:1 meetings and add them to docs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan recently ended meetings once")
    _add_common_args(scan)
    scan.add_argument("--lookback-hours", type=int, default=8)
    scan.add_argument("--max-results", type=int, default=250)
    scan.add_argument("--person", help="Only process a watched person by name or email")

    watch = subparsers.add_parser("watch", help="Poll until assets are ready or timeout")
    _add_common_args(watch)
    watch.add_argument("--lookback-hours", type=int, default=8)
    watch.add_argument("--max-results", type=int, default=250)
    watch.add_argument("--poll-seconds", type=int, default=300)
    watch.add_argument("--timeout-minutes", type=int, default=120)
    watch.add_argument("--person", help="Only process a watched person by name or email")

    event = subparsers.add_parser("event", help="Process a specific calendar event ID")
    _add_common_args(event)
    event.add_argument("event_id")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "scan":
            results = scan_events(
                lookback_hours=args.lookback_hours,
                watchlist_path=args.watchlist,
                state_path=args.state,
                apply=args.apply,
                require=args.require,
                include_transcript=args.include_transcript,
                match_window_minutes=args.match_window_minutes,
                max_results=args.max_results,
                note_style=args.note_style,
                check_docs=not args.no_check_docs,
                person_filter=args.person,
            )
            print_results(results)
            return

        if args.command == "event":
            result = process_single_event(
                event_id=args.event_id,
                watchlist_path=args.watchlist,
                state_path=args.state,
                apply=args.apply,
                require=args.require,
                include_transcript=args.include_transcript,
                match_window_minutes=args.match_window_minutes,
                note_style=args.note_style,
                check_docs=not args.no_check_docs,
            )
            print_results([result])
            return

        if args.command == "watch":
            deadline = time.time() + args.timeout_minutes * 60
            while True:
                results = scan_events(
                    lookback_hours=args.lookback_hours,
                    watchlist_path=args.watchlist,
                    state_path=args.state,
                    apply=args.apply,
                    require=args.require,
                    include_transcript=args.include_transcript,
                    match_window_minutes=args.match_window_minutes,
                    max_results=args.max_results,
                    note_style=args.note_style,
                    check_docs=not args.no_check_docs,
                    person_filter=args.person,
                )
                print_results(results)
                if results and all(r.get("status") not in {"pending"} for r in results):
                    return
                if time.time() >= deadline:
                    print("Timed out before all watched assets were ready.", file=sys.stderr)
                    sys.exit(2)
                time.sleep(args.poll_seconds)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Tests for Zoom 1:1 asset watcher helpers."""

import unittest
from datetime import datetime, timezone

from sidekick.clients import zoom_1on1_assets as assets


def _event(
    event_id="event-1",
    summary="Alice-Manager 1:1",
    attendees=None,
    description="",
    attachments=None,
    start="2026-05-19T12:05:00-04:00",
    end="2026-05-19T12:30:00-04:00",
    conference_id="12345678901",
):
    attendees = attendees or [
        {"email": "alice@example.com"},
        {"email": "manager@example.com", "self": True},
    ]
    conference_data = {}
    if conference_id:
        conference_data = {
            "entryPoints": [
                {"entryPointType": "video", "uri": f"https://example.zoom.us/j/{conference_id}"}
            ]
        }
    return {
        "id": event_id,
        "summary": summary,
        "attendees": attendees,
        "description": description,
        "attachments": attachments or [],
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "conferenceData": conference_data,
    }


def _watchlist():
    return {
        "self_email": "manager@example.com",
        "people": [
            {"name": "Alice", "email": "alice@example.com", "summary_patterns": []},
            {"name": "Peer", "email": "peer@example.com", "summary_patterns": ["Peer / Manager"]},
        ],
        "people_by_email": {
            "alice@example.com": {"name": "Alice", "email": "alice@example.com", "summary_patterns": []},
            "peer@example.com": {
                "name": "Peer",
                "email": "peer@example.com",
                "summary_patterns": ["Peer / Manager"],
            },
        },
    }


class TestEligibility(unittest.TestCase):
    def test_allows_ended_two_person_watched_one_on_one(self):
        event = _event()
        now = datetime(2026, 5, 19, 17, 0, tzinfo=timezone.utc)

        eligible = assets.iter_eligible_events([event], _watchlist(), now)

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0][1]["email"], "alice@example.com")

    def test_excludes_group_meeting_with_watched_person(self):
        event = _event(attendees=[
            {"email": "alice@example.com"},
            {"email": "bob@example.com"},
            {"email": "manager@example.com", "self": True},
        ])
        now = datetime(2026, 5, 19, 17, 0, tzinfo=timezone.utc)

        eligible = assets.iter_eligible_events([event], _watchlist(), now)

        self.assertEqual(eligible, [])

    def test_allows_explicit_summary_pattern_without_1on1_title(self):
        event = _event(
            summary="Peer / Manager",
            attendees=[
                {"email": "peer@example.com"},
                {"email": "manager@example.com", "self": True},
            ],
            description="Purpose: peer 1:1",
        )
        person = assets.find_allowed_counterpart(event, _watchlist())

        self.assertTrue(assets.is_one_on_one_event(event, person))

    def test_person_filter_matches_name_email_and_summary(self):
        event = _event(summary="Peer / Manager")
        person = {"name": "Peer Person", "email": "peer@example.com"}

        self.assertTrue(assets.person_matches_filter(event, person, "peer"))
        self.assertTrue(assets.person_matches_filter(event, person, "example.com"))
        self.assertTrue(assets.person_matches_filter(event, person, "manager"))
        self.assertFalse(assets.person_matches_filter(event, person, "alice"))


class TestDocResolution(unittest.TestCase):
    def test_resolves_doc_from_attachment(self):
        event = _event(attachments=[{
            "mimeType": "application/vnd.google-apps.document",
            "fileId": "doc123",
            "fileUrl": "https://docs.google.com/document/d/doc123/edit?tab=t.0",
            "title": "Alice / Manager 1:1",
        }])

        target = assets.resolve_doc_target(event, {"name": "Alice", "email": "alice@example.com"})

        self.assertEqual(target["document_id"], "doc123")
        self.assertEqual(target["tab_id"], "t.0")

    def test_resolves_doc_from_description(self):
        event = _event(
            description=(
                '<a href="https://docs.google.com/document/d/docABC/edit?usp=sharing">'
                "Alice-Manager 1:1</a>"
            )
        )

        target = assets.resolve_doc_target(event, {"name": "Alice", "email": "alice@example.com"})

        self.assertEqual(target["document_id"], "docABC")
        self.assertIsNone(target["tab_id"])


class FakeZoom:
    def __init__(self, instances):
        self.instances = instances

    def get_past_meeting_instances(self, meeting_id):
        return self.instances


class TestZoomMatching(unittest.TestCase):
    def test_matches_closest_instance_within_window(self):
        zoom = FakeZoom([
            {"uuid": "old", "start_time": "2026-05-05T16:05:00Z"},
            {"uuid": "current", "start_time": "2026-05-19T16:06:00Z"},
        ])
        event = _event(start="2026-05-19T12:05:00-04:00")

        instance = assets.match_zoom_instance(
            zoom,
            "12345678901",
            assets.event_start(event),
            match_window_minutes=15,
        )

        self.assertEqual(instance["uuid"], "current")

    def test_returns_none_when_no_instance_in_window(self):
        zoom = FakeZoom([{"uuid": "old", "start_time": "2026-05-05T16:05:00Z"}])
        event = _event(start="2026-05-19T12:05:00-04:00")

        instance = assets.match_zoom_instance(
            zoom,
            "12345678901",
            assets.event_start(event),
            match_window_minutes=15,
        )

        self.assertIsNone(instance)


class TestRenderingAndWrites(unittest.TestCase):
    def test_render_link_note_contains_only_date_and_summary_link(self):
        event = _event(event_id="event-123")
        note = assets.render_meeting_note(
            event,
            {"name": "Alice", "email": "alice@example.com"},
            "uuid-123",
            {
                "summary": {
                    "summary_doc_url": "https://hub.zoom.us/doc/abc",
                    "summary_overview": "Discussed priorities.",
                    "next_steps": ["Alice: Send update."],
                },
                "transcript": None,
            },
        )

        self.assertIn("Summary for 05/19/2026: https://hub.zoom.us/doc/abc", note)
        self.assertNotIn("Discussed priorities.", note)
        self.assertNotIn("Zoom asset id:", note)

    def test_render_note_contains_summary_next_steps_and_marker(self):
        event = _event(event_id="event-123")
        note = assets.render_meeting_note(
            event,
            {"name": "Alice", "email": "alice@example.com"},
            "uuid-123",
            {
                "summary": {
                    "summary_doc_url": "https://hub.zoom.us/doc/abc",
                    "summary_overview": "Discussed priorities.",
                    "summary_details": [{"label": "Planning"}],
                    "next_steps": ["Alice: Send update."],
                },
                "transcript": None,
            },
            note_style="full",
        )

        self.assertIn("Summary: https://hub.zoom.us/doc/abc", note)
        self.assertIn("- Alice: Send update.", note)
        self.assertIn("Zoom asset id: zoom-1on1-assets/event-123/uuid-123", note)

    def test_process_event_reports_pending_when_summary_has_no_doc_url(self):
        class FakeZoomNoDocUrl(FakeZoom):
            def get_meeting_summary(self, meeting_uuid):
                return {"summary_overview": "No link is available yet."}

        event = _event(
            attachments=[{
                "mimeType": "application/vnd.google-apps.document",
                "fileId": "doc123",
                "fileUrl": "https://docs.google.com/document/d/doc123/edit?tab=t.0",
                "title": "Alice / Manager 1:1",
            }],
        )
        result = assets.process_event(
            event,
            {"name": "Alice", "email": "alice@example.com"},
            FakeZoomNoDocUrl([{"uuid": "current", "start_time": "2026-05-19T16:06:00Z"}]),
            object(),
            {"processed": {}},
            apply=False,
            require="summary",
            include_transcript=False,
            match_window_minutes=15,
            note_style="link",
            check_docs=True,
        )

        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["reason"], "Zoom summary has no summary_doc_url")

    def test_append_skips_when_marker_exists(self):
        class FakeDocs:
            def read_document(self, document_id, tab_id=None):
                return "already here\nZoom asset id: zoom-1on1-assets/event-123/uuid-123\n"

        status = assets.append_note_to_doc(
            FakeDocs(),
            "doc123",
            None,
            "new note",
            "Zoom asset id: zoom-1on1-assets/event-123/uuid-123",
        )

        self.assertEqual(status, "already-present")

    def test_append_skips_when_summary_doc_url_already_exists(self):
        class FakeDocs:
            def read_document(self, document_id, tab_id=None):
                return "Summary: https://hub.zoom.us/doc/summaryABC?from=hub"

        status = assets.append_note_to_doc(
            FakeDocs(),
            "doc123",
            None,
            "new note",
            "missing marker",
            summary_url="https://docs.zoom.us/doc/summaryABC",
        )

        self.assertEqual(status, "already-present")

    def test_append_uses_end_index_and_tab_id(self):
        class FakeDocs:
            def __init__(self):
                self.requests = None
                self.written = False

            def read_document(self, document_id, tab_id=None):
                if self.written:
                    return "current text\nmissing marker"
                return "current text"

            def get_document(self, document_id, include_tabs=True):
                return {
                    "tabs": [{
                        "tabProperties": {"tabId": "t.0"},
                        "documentTab": {"body": {"content": [{"endIndex": 12}]}},
                    }]
                }

            def batch_update(self, document_id, requests):
                self.requests = requests
                self.written = True

        fake_docs = FakeDocs()

        status = assets.append_note_to_doc(
            fake_docs,
            "doc123",
            "t.0",
            "\nnew note",
            "missing marker",
            summary_url="https://example.com/summary",
        )

        self.assertEqual(status, "inserted")
        insert = fake_docs.requests[0]["insertText"]
        self.assertEqual(insert["location"], {"index": 11, "tabId": "t.0"})
        self.assertEqual(insert["text"], "\nnew note")

    def test_append_can_insert_after_date_heading(self):
        class FakeDocs:
            def __init__(self):
                self.requests = None
                self.written = False

            def read_document(self, document_id, tab_id=None):
                if self.written:
                    return "May 19, 2026\nmissing marker\nbody"
                return "May 19, 2026\nbody"

            def get_document(self, document_id, include_tabs=True):
                return {
                    "tabs": [{
                        "tabProperties": {"tabId": "t.0"},
                        "documentTab": {
                            "body": {
                                "content": [
                                    {
                                        "startIndex": 10,
                                        "endIndex": 12,
                                        "paragraph": {
                                            "elements": [
                                                {
                                                    "startIndex": 10,
                                                    "endIndex": 11,
                                                    "dateElement": {
                                                        "dateElementProperties": {
                                                            "displayText": "May 19, 2026"
                                                        }
                                                    },
                                                },
                                                {
                                                    "startIndex": 11,
                                                    "endIndex": 12,
                                                    "textRun": {"content": "\n"},
                                                },
                                            ]
                                        },
                                    },
                                    {"startIndex": 12, "endIndex": 20, "paragraph": {"elements": []}},
                                ]
                            }
                        },
                    }]
                }

            def batch_update(self, document_id, requests):
                self.requests = requests
                self.written = True

        fake_docs = FakeDocs()

        status = assets.append_note_to_doc(
            fake_docs,
            "doc123",
            "t.0",
            "missing marker https://example.com/summary\n\n",
            "missing marker",
            summary_url="https://example.com/summary",
            insert_after_date="May 19, 2026",
        )

        self.assertEqual(status, "inserted")
        insert = fake_docs.requests[0]["insertText"]
        self.assertEqual(insert["location"], {"index": 12, "tabId": "t.0"})
        self.assertIn("deleteParagraphBullets", fake_docs.requests[1])
        self.assertIn("updateParagraphStyle", fake_docs.requests[2])
        link = fake_docs.requests[3]["updateTextStyle"]
        self.assertEqual(link["range"], {"tabId": "t.0", "startIndex": 27, "endIndex": 54})
        self.assertEqual(link["textStyle"]["link"]["url"], "https://example.com/summary")

    def test_append_can_insert_after_weekday_date_heading(self):
        class FakeDocs:
            def __init__(self):
                self.requests = None
                self.written = False

            def read_document(self, document_id, tab_id=None):
                if self.written:
                    return "Friday May 15, 2026\nmissing marker\nbody"
                return "Friday May 15, 2026\nbody"

            def get_document(self, document_id, include_tabs=True):
                return {
                    "tabs": [{
                        "tabProperties": {"tabId": "t.0"},
                        "documentTab": {
                            "body": {
                                "content": [
                                    {
                                        "startIndex": 10,
                                        "endIndex": 31,
                                        "paragraph": {
                                            "elements": [
                                                {
                                                    "startIndex": 10,
                                                    "endIndex": 31,
                                                    "textRun": {"content": "Friday May 15, 2026\n"},
                                                },
                                            ]
                                        },
                                    },
                                    {"startIndex": 31, "endIndex": 40, "paragraph": {"elements": []}},
                                ]
                            }
                        },
                    }]
                }

            def batch_update(self, document_id, requests):
                self.requests = requests
                self.written = True

        fake_docs = FakeDocs()

        status = assets.append_note_to_doc(
            fake_docs,
            "doc123",
            "t.0",
            "missing marker\n\n",
            "missing marker",
            insert_after_date="May 15, 2026",
        )

        self.assertEqual(status, "inserted")
        insert = fake_docs.requests[0]["insertText"]
        self.assertEqual(insert["location"], {"index": 31, "tabId": "t.0"})

    def test_append_can_insert_after_abbreviated_date_heading(self):
        class FakeDocs:
            def __init__(self):
                self.requests = None
                self.written = False

            def read_document(self, document_id, tab_id=None):
                if self.written:
                    return "Tuesday Mar 03, 2026\nmissing marker\nbody"
                return "Tuesday Mar 03, 2026\nbody"

            def get_document(self, document_id, include_tabs=True):
                return {
                    "tabs": [{
                        "tabProperties": {"tabId": "t.0"},
                        "documentTab": {
                            "body": {
                                "content": [
                                    {
                                        "startIndex": 10,
                                        "endIndex": 31,
                                        "paragraph": {
                                            "elements": [
                                                {
                                                    "startIndex": 10,
                                                    "endIndex": 31,
                                                    "textRun": {"content": "Tuesday Mar 03, 2026\n"},
                                                },
                                            ]
                                        },
                                    },
                                    {"startIndex": 31, "endIndex": 40, "paragraph": {"elements": []}},
                                ]
                            }
                        },
                    }]
                }

            def batch_update(self, document_id, requests):
                self.requests = requests
                self.written = True

        fake_docs = FakeDocs()

        status = assets.append_note_to_doc(
            fake_docs,
            "doc123",
            "t.0",
            "missing marker\n\n",
            "missing marker",
            insert_after_date="March 3, 2026",
        )

        self.assertEqual(status, "inserted")
        insert = fake_docs.requests[0]["insertText"]
        self.assertEqual(insert["location"], {"index": 31, "tabId": "t.0"})

    def test_date_key_matches_ordinal_and_numeric_dates(self):
        self.assertEqual(
            assets._date_key("Tuesday, March 3rd, 2026"),
            assets._date_key("03/03/2026"),
        )

    def test_append_raises_when_target_tab_readback_misses_note(self):
        class FakeDocs:
            def read_document(self, document_id, tab_id=None):
                return "current text"

            def get_document(self, document_id, include_tabs=True):
                return {
                    "tabs": [{
                        "tabProperties": {"tabId": "t.0"},
                        "documentTab": {"body": {"content": [{"endIndex": 12}]}},
                    }]
                }

            def batch_update(self, document_id, requests):
                pass

        with self.assertRaises(RuntimeError):
            assets.append_note_to_doc(
                FakeDocs(),
                "doc123",
                "t.0",
                "\nnew note",
                "missing marker",
            )


if __name__ == "__main__":
    unittest.main()

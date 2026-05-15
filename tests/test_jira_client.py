"""Tests for Jira client transition helpers."""
import unittest
from unittest.mock import call, patch

from sidekick.clients.jira import JiraClient, _parse_transition_args


def _issue(status):
    return {
        "key": "PROJ-123",
        "fields": {
            "status": {
                "name": status,
                "statusCategory": {"name": "In Progress"},
            },
        },
    }


def _transition(transition_id, name, to_status, fields=None):
    return {
        "id": transition_id,
        "name": name,
        "to": {
            "name": to_status,
            "statusCategory": {"name": "Done"},
        },
        "fields": fields or {},
    }


class TestJiraTransitions(unittest.TestCase):
    """Tests for Jira transition methods."""

    def setUp(self):
        self.client = JiraClient(
            base_url="https://example.atlassian.net",
            email="alice@example.com",
            api_token="token",
        )

    @patch.object(JiraClient, "_request")
    def test_list_transitions_expands_fields(self, mock_request):
        """list_transitions fetches transitions with required field metadata."""
        mock_request.return_value = {
            "transitions": [_transition("91", "Done", "Done")]
        }

        transitions = self.client.list_transitions("PROJ-123")

        self.assertEqual(len(transitions), 1)
        mock_request.assert_called_once_with(
            "GET",
            "/rest/api/3/issue/PROJ-123/transitions",
            params={"expand": "transitions.fields"},
        )

    @patch.object(JiraClient, "_request")
    def test_transition_issue_matches_destination_status(self, mock_request):
        """transition_issue can match by the target status name."""
        mock_request.side_effect = [
            _issue("In Progress"),
            {"transitions": [_transition("91", "Done", "Done")]},
            None,
            _issue("Done"),
        ]

        result = self.client.transition_issue("PROJ-123", "Done")

        self.assertEqual(result["before_status"], "In Progress")
        self.assertEqual(result["after_status"], "Done")
        self.assertTrue(result["changed"])
        self.assertEqual(
            mock_request.call_args_list,
            [
                call("GET", "/rest/api/3/issue/PROJ-123"),
                call(
                    "GET",
                    "/rest/api/3/issue/PROJ-123/transitions",
                    params={"expand": "transitions.fields"},
                ),
                call(
                    "POST",
                    "/rest/api/3/issue/PROJ-123/transitions",
                    json_data={"transition": {"id": "91"}},
                ),
                call("GET", "/rest/api/3/issue/PROJ-123"),
            ],
        )

    @patch.object(JiraClient, "_request")
    def test_transition_issue_matches_transition_name(self, mock_request):
        """transition_issue can match by transition name."""
        mock_request.side_effect = [
            _issue("Open"),
            {"transitions": [_transition("101", "Start Review", "In Review")]},
            None,
            _issue("In Review"),
        ]

        result = self.client.transition_issue("PROJ-123", "Start Review")

        self.assertEqual(result["target_status"], "In Review")
        self.assertEqual(result["transition"]["id"], "101")

    @patch.object(JiraClient, "_request")
    def test_transition_issue_noops_when_already_in_status(self, mock_request):
        """No remote transition is posted if the issue is already in target status."""
        mock_request.return_value = _issue("Done")

        result = self.client.transition_issue("PROJ-123", "Done")

        self.assertFalse(result["changed"])
        self.assertIsNone(result["transition"])
        mock_request.assert_called_once_with("GET", "/rest/api/3/issue/PROJ-123")

    @patch.object(JiraClient, "_request")
    def test_transition_issue_refuses_ambiguous_targets(self, mock_request):
        """Ambiguous transition targets fail before posting a transition."""
        mock_request.side_effect = [
            _issue("In Progress"),
            {
                "transitions": [
                    _transition("91", "Finish", "Done"),
                    _transition("92", "Done", "Done"),
                ],
            },
        ]

        with self.assertRaises(ValueError) as ctx:
            self.client.transition_issue("PROJ-123", "Done")

        self.assertIn("Ambiguous", str(ctx.exception))
        self.assertEqual(mock_request.call_count, 2)

    @patch.object(JiraClient, "_request")
    def test_transition_issue_refuses_required_fields(self, mock_request):
        """Transitions requiring extra fields fail with a clear message."""
        mock_request.side_effect = [
            _issue("In Progress"),
            {
                "transitions": [
                    _transition(
                        "111",
                        "Duplicate",
                        "Duplicate",
                        fields={"parent": {"required": True}},
                    ),
                ],
            },
        ]

        with self.assertRaises(ValueError) as ctx:
            self.client.transition_issue("PROJ-123", "Duplicate")

        self.assertIn("requires fields: parent", str(ctx.exception))
        self.assertEqual(mock_request.call_count, 2)

    @patch.object(JiraClient, "_request")
    def test_transition_issue_dry_run_does_not_post(self, mock_request):
        """Dry run reports the matching transition without applying it."""
        mock_request.side_effect = [
            _issue("In Progress"),
            {"transitions": [_transition("91", "Done", "Done")]},
        ]

        result = self.client.transition_issue("PROJ-123", "Done", dry_run=True)

        self.assertFalse(result["changed"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["target_status"], "Done")
        self.assertEqual(mock_request.call_count, 2)

    @patch.object(JiraClient, "_request")
    def test_complete_issue_prefers_complete_over_done(self, mock_request):
        """complete_issue uses Complete before falling back to Done."""
        mock_request.side_effect = [
            _issue("In Progress"),
            {
                "transitions": [
                    _transition("91", "Done", "Done"),
                    _transition("151", "Complete", "Complete"),
                ],
            },
            None,
            _issue("Complete"),
        ]

        result = self.client.complete_issue("PROJ-123")

        self.assertEqual(result["target_status"], "Complete")
        self.assertEqual(result["transition"]["id"], "151")

    @patch.object(JiraClient, "_request")
    def test_complete_issue_falls_back_to_done(self, mock_request):
        """complete_issue uses Done when Complete is not available."""
        mock_request.side_effect = [
            _issue("In Progress"),
            {"transitions": [_transition("91", "Done", "Done")]},
            None,
            _issue("Done"),
        ]

        result = self.client.complete_issue("PROJ-123")

        self.assertEqual(result["target_status"], "Done")
        self.assertEqual(result["transition"]["id"], "91")


class TestJiraTransitionCliHelpers(unittest.TestCase):
    """Tests for CLI parsing helpers."""

    def test_parse_transition_args_allows_unquoted_multi_word_target(self):
        dry_run, target = _parse_transition_args(["In", "Review", "--dry-run"])

        self.assertTrue(dry_run)
        self.assertEqual(target, "In Review")


if __name__ == "__main__":
    unittest.main()

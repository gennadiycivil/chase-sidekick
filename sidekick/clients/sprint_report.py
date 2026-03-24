"""Sprint Report API Client - fetches Core Sprint Reports from core-analytics-server."""

import json
import sys
import urllib.request
import urllib.error
from typing import Optional


class SprintReportClient:
    """Client for the Core Sprint Report API (core-analytics-server.pp.dropbox.com).

    Auth: Cookie-based via Dropbox SSO. Requires pp_session cookies exported
    from a browser session. Store in .env as SPRINT_REPORT_COOKIES.
    """

    BASE_URL = "https://core-analytics-server.pp.dropbox.com/api/sprintreports"

    def __init__(self, cookies: str, timeout: int = 30):
        """Initialize client.

        Args:
            cookies: Cookie string for authentication (from browser session).
                     Minimum required: ppa, pp_samesite, bjar, __Secure-untrusted_session, t, blid
            timeout: Request timeout in seconds
        """
        self.cookies = cookies
        self.timeout = timeout

    def _request(self, path: str) -> dict:
        """Make authenticated GET request to the API.

        Args:
            path: API path (appended to BASE_URL)

        Returns:
            Parsed JSON response
        """
        url = f"{self.BASE_URL}/{path}"
        req = urllib.request.Request(url)
        req.add_header("Cookie", self.cookies)
        req.add_header("Referer", "https://core-analytics-server.pp.dropbox.com/sprintreports")
        req.add_header("Accept", "*/*")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            raise RuntimeError(f"HTTP {e.code}: {body[:200]}") from e

    def get_dates(self) -> list:
        """Get available sprint report dates.

        Returns:
            List of dicts with 'date' and 'label' keys, plus 'default' date.
        """
        return self._request("dates")

    def get_report(self, date: Optional[str] = None) -> dict:
        """Get full sprint report for a given date.

        Args:
            date: Report date (e.g. '2026-03-16'). If None, uses default (latest).

        Returns:
            Full report dict with sections, banners, epics, etc.
        """
        if date is None:
            dates_resp = self.get_dates()
            date = dates_resp["default"]
        return self._request(f"report/{date}")

    def get_team_report(self, date: Optional[str] = None,
                        section: str = "Core Experience",
                        team: str = "Browse & Navigate Web experience") -> Optional[dict]:
        """Get report data for a specific team banner.

        Args:
            date: Report date. If None, uses latest.
            section: Section name (e.g. 'Core Experience')
            team: Banner/team label (e.g. 'Browse & Navigate Web experience')

        Returns:
            Banner dict for the team, or None if not found
        """
        report = self.get_report(date)
        for s in report["sections"]:
            if s["name"] == section:
                for banner in s["banners"]:
                    if banner["label"] == team:
                        return banner
        return None


def _format_summary(banner: dict, sprint_label: str = "") -> str:
    """Format team banner data into readable summary."""
    lines = []
    label = banner["label"]
    cards = banner["summary_cards"]
    meta = banner.get("metadata", {})

    if sprint_label:
        lines.append(f"Sprint: {sprint_label}")
    lines.append(f"Team: {label}")
    if meta.get("sprint_name"):
        lines.append(f"Sprint Name: {meta['sprint_name']} ({meta.get('sprint_start', '')} to {meta.get('sprint_end', '')})")
    lines.append("")

    # Summary cards
    lines.append(f"Issues Done: {cards['issue_done']}/{cards['issue_total']} ({cards['issue_pct']}%)")
    lines.append(f"Epics Tracked: {cards['epics_tracked']}")
    lines.append(f"Epics Completed: {cards['epics_completed']}")
    lines.append(f"Epics In Progress: {cards['epics_in_progress']}")

    # Quarterly epic counts
    epic_counts = banner.get("epic_counts", {})
    if epic_counts:
        lines.append(f"Quarterly Epics: {epic_counts.get('done', 0)}/{epic_counts.get('total', 0)} done")
    lines.append("")

    # Executive summary
    exec_summary = banner.get("executive_summary", {})
    if exec_summary.get("bullets"):
        lines.append("Executive Summary:")
        for bullet in exec_summary["bullets"]:
            lines.append(f"  - {bullet}")
        lines.append("")

    # Completed epics
    completed = banner.get("completed_epics", [])
    if completed:
        lines.append(f"Completed Epics ({len(completed)}):")
        for epic in completed:
            e = epic["epic"]
            assignee = epic.get("assignee", "")
            hours = epic.get("estimated_hours", "-")
            children = f"{epic.get('done_children', 0)}/{epic.get('total_children', 0)}"
            lines.append(f"  {e['key']}: {e['summary']} [{e['status_name']}] ({assignee}) {hours}h {children}")
            if epic.get("parent"):
                p = epic["parent"]
                lines.append(f"    RI: {p['key']} {p['summary']} [{p['status_name']}]")
        lines.append("")

    # Epic completion percentage
    pct = banner.get("epic_pct_complete", [])
    if pct:
        in_progress = [item for item in pct if item.get("epic", {}).get("status_category") != "done"]
        if in_progress:
            lines.append(f"Epics In Progress ({len(in_progress)}):")
            for item in in_progress:
                e = item["epic"]
                done = item.get("done_children", 0)
                total = item.get("total_children", 0)
                pct_val = f"{round(done/total*100)}%" if total > 0 else "0%"
                assignee = item.get("assignee", "")
                line = f"  {e['key']}: {e['summary']} ({done}/{total} = {pct_val})"
                if assignee:
                    line += f" ({assignee})"
                lines.append(line)
            lines.append("")

    # Hours by workstream (bar chart)
    bar = banner.get("bar_chart", [])
    if bar:
        lines.append("Hours by Workstream:")
        for item in bar:
            lines.append(f"  {item['label']}: {item['hours']}h")
        lines.append("")

    # At risk items
    at_risk = banner.get("at_risk_items", [])
    if at_risk:
        lines.append(f"At Risk Items ({len(at_risk)}):")
        for item in at_risk:
            lines.append(f"  {item.get('key', '')}: {item.get('summary', '')} [{item.get('status_name', '')}]")
        lines.append("")

    # Unlinked issues
    unlinked = banner.get("unlinked_issues", [])
    if unlinked:
        lines.append(f"Unlinked Issues ({len(unlinked)}):")
        for item in unlinked:
            lines.append(f"  {item.get('key', '')}: {item.get('summary', '')}")
        lines.append("")

    return "\n".join(lines)


def _format_workstream_tree(banner: dict) -> str:
    """Format workstream tree (RI -> Epic -> Task breakdown)."""
    lines = []
    tree = banner.get("workstream_tree", [])
    if not tree:
        return "No workstream tree data."

    for node in tree:
        indent = "  " * node.get("level", 0)
        key = node.get("key", "")
        summary = node.get("summary", "")
        status = node.get("status_name", "")
        assignee = node.get("assignee", "")
        hours = node.get("hours", "")
        done = node.get("done_children", 0)
        total = node.get("total_children", 0)
        commits = node.get("commits", 0)
        prs = node.get("prs", 0)

        line = f"{indent}{key}: {summary} [{status}]"
        if assignee:
            line += f" ({assignee})"
        if hours:
            line += f" {hours}h"
        if total > 0:
            line += f" {done}/{total}"
        if commits:
            line += f" {commits}c/{prs}pr"
        lines.append(line)

        # Recurse into children
        for child in node.get("children", []):
            child_indent = "  " * child.get("level", node.get("level", 0) + 1)
            ck = child.get("key", "")
            cs = child.get("summary", "")
            cst = child.get("status_name", "")
            ca = child.get("assignee", "")
            ch = child.get("hours", "")
            cd = child.get("done_children", 0)
            ct = child.get("total_children", 0)

            cline = f"{child_indent}{ck}: {cs} [{cst}]"
            if ca:
                cline += f" ({ca})"
            if ch:
                cline += f" {ch}h"
            if ct > 0:
                cline += f" {cd}/{ct}"
            lines.append(cline)

    return "\n".join(lines)


def main():
    """CLI entry point."""
    from sidekick.config import _load_env_file, _get_env

    env_vars = _load_env_file()
    cookies = _get_env("SPRINT_REPORT_COOKIES", env_vars)
    if not cookies:
        print("Error: SPRINT_REPORT_COOKIES not set in .env", file=sys.stderr)
        print("Export cookies from browser: ppa, pp_samesite, bjar, __Secure-untrusted_session, t, blid", file=sys.stderr)
        print('Format: SPRINT_REPORT_COOKIES="ppa=...;pp_samesite=...;bjar=...;..."', file=sys.stderr)
        sys.exit(1)

    client = SprintReportClient(cookies)

    if len(sys.argv) < 2:
        print("Usage: python -m sidekick.clients.sprint_report <command> [args]")
        print("Commands:")
        print("  dates                              List available sprint dates")
        print("  summary [date] [section] [team]    Show team summary")
        print("  tree [date] [section] [team]       Show workstream tree")
        print("  raw [date] [section] [team]        Dump raw JSON for team")
        sys.exit(1)

    command = sys.argv[1]

    if command == "dates":
        result = client.get_dates()
        print(f"Default: {result['default']}")
        for d in result["dates"]:
            marker = " (default)" if d["date"] == result["default"] else ""
            print(f"  {d['date']}: {d['label']}{marker}")

    elif command in ("summary", "tree", "raw"):
        date = sys.argv[2] if len(sys.argv) > 2 else None
        section = sys.argv[3] if len(sys.argv) > 3 else "Core Experience"
        team = sys.argv[4] if len(sys.argv) > 4 else "Browse & Navigate Web experience"

        # Get sprint label
        report = client.get_report(date)
        sprint_label = report.get("sprint_label", "")

        banner = None
        for s in report["sections"]:
            if s["name"] == section:
                for b in s["banners"]:
                    if b["label"] == team:
                        banner = b
                        break

        if not banner:
            print(f"Team '{team}' not found in section '{section}'", file=sys.stderr)
            print("Available sections and teams:", file=sys.stderr)
            for s in report["sections"]:
                print(f"  {s['name']}:", file=sys.stderr)
                for b in s["banners"]:
                    print(f"    - {b['label']}", file=sys.stderr)
            sys.exit(1)

        if command == "summary":
            print(_format_summary(banner, sprint_label))
        elif command == "tree":
            print(_format_workstream_tree(banner))
        elif command == "raw":
            print(json.dumps(banner, indent=2))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

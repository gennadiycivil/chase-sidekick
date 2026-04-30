"""PTO Tracker Client - reads team PTO from Google Calendar."""

import sys
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class PTOClient:
    """PTO tracker that reads from Google Calendar.

    Relies on Workday -> Google Calendar sync for approved PTO.
    Parses calendar events matching pattern: "{Name} - Time-Off"
    """

    # Team roster - names to match in calendar events
    TEAM_MEMBERS = [
        "Nick Larson",
        "Mike Moser",
        "Durgesh Patel",
        "Xiaoxi Jin",
        "Anthony Perello",
        "Alex Yurowkin",
        "Albert Caldarelli",
        "Bree Devries",
        "Ryan Ward",
        "Calvin Lee",
        "Wyatt Richter",
        "Catherine Lee",
        "Karen Choi",
        "Swee Yong Chiah",
        "Nathan Aun",
        "Summer Sheldon",
        "Dipo Arowona",
        "Ben Potter"  # 50% on team
    ]

    def __init__(self, gcalendar_client):
        """Initialize PTO client with Google Calendar client.

        Args:
            gcalendar_client: Instance of GCalendarClient
        """
        self.gcal = gcalendar_client

    def _parse_pto_event(self, event: dict) -> Optional[Dict]:
        """Parse a calendar event to extract PTO information.

        Args:
            event: Calendar event dict from Google Calendar API

        Returns:
            Dict with {name, start_date, end_date, is_all_day} or None if not PTO
        """
        summary = event.get("summary", "")

        # Match pattern: "FirstName LastName - Time-Off"
        match = re.match(r"^(.+?)\s*-\s*Time-Off", summary)
        if not match:
            return None

        name = match.group(1).strip()

        # Only include team members
        if name not in self.TEAM_MEMBERS:
            return None

        # Parse date - can be all-day (date only) or timed (dateTime)
        start = event.get("start", {})
        end = event.get("end", {})

        if "date" in start:
            # All-day event
            start_date = datetime.strptime(start["date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(end["date"], "%Y-%m-%d").date()
            # Google Calendar end date is exclusive for all-day events
            end_date = end_date - timedelta(days=1)
            is_all_day = True
        elif "dateTime" in start:
            # Timed event - extract date only
            start_date = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).date()
            end_date = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00")).date()
            is_all_day = False
        else:
            return None

        return {
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "is_all_day": is_all_day
        }

    def get_pto_in_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get PTO events for team members within date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)

        Returns:
            List of dicts with {name, start_date, end_date, is_all_day}
        """
        # Convert to RFC3339 timestamps
        time_min = start_date.strftime("%Y-%m-%dT00:00:00Z")
        time_max = (end_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

        # Fetch calendar events
        events = self.gcal.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=200  # Enough for ~10 team members * ~20 days
        )

        # Parse and filter PTO events
        pto_events = []
        for event in events:
            pto = self._parse_pto_event(event)
            if pto:
                pto_events.append(pto)

        return pto_events

    def get_pto_today(self) -> List[Dict]:
        """Get team members on PTO today.

        Returns:
            List of dicts with {name, start_date, end_date, is_all_day}
        """
        today = datetime.now().date()
        return self.get_pto_in_range(
            datetime.combine(today, datetime.min.time()),
            datetime.combine(today, datetime.min.time())
        )

    def get_pto_tomorrow(self) -> List[Dict]:
        """Get team members on PTO tomorrow.

        Returns:
            List of dicts with {name, start_date, end_date, is_all_day}
        """
        tomorrow = datetime.now().date() + timedelta(days=1)
        return self.get_pto_in_range(
            datetime.combine(tomorrow, datetime.min.time()),
            datetime.combine(tomorrow, datetime.min.time())
        )

    def get_pto_week(self) -> List[Dict]:
        """Get team PTO for next 7 days.

        Returns:
            List of dicts with {name, start_date, end_date, is_all_day}
        """
        today = datetime.now().date()
        end = today + timedelta(days=7)
        return self.get_pto_in_range(
            datetime.combine(today, datetime.min.time()),
            datetime.combine(end, datetime.min.time())
        )

    def get_pto_sprint(self, sprint_days: int = 10) -> List[Dict]:
        """Get team PTO for next sprint (default 10 business days = 2 weeks).

        Args:
            sprint_days: Number of business days in sprint (default 10)

        Returns:
            List of dicts with {name, start_date, end_date, is_all_day}
        """
        today = datetime.now().date()

        # Calculate end date (sprint_days business days ahead)
        current = today
        business_days_count = 0
        while business_days_count < sprint_days:
            current += timedelta(days=1)
            # Skip weekends (Monday=0, Sunday=6)
            if current.weekday() < 5:
                business_days_count += 1

        return self.get_pto_in_range(
            datetime.combine(today, datetime.min.time()),
            datetime.combine(current, datetime.min.time())
        )


def _format_pto_summary(pto_events: List[Dict], start_date: datetime, end_date: datetime) -> str:
    """Format PTO events into human-readable summary.

    Args:
        pto_events: List of PTO event dicts
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Formatted summary string
    """
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    lines = [f"PTO Summary ({start_str} to {end_str}):"]

    if not pto_events:
        lines.append("• No team members on PTO")
        return "\n".join(lines)

    # Group by person
    by_person: Dict[str, List[Dict]] = {}
    for event in pto_events:
        name = event["name"]
        if name not in by_person:
            by_person[name] = []
        by_person[name].append(event)

    # Format each person's PTO
    for name in sorted(by_person.keys()):
        person_events = by_person[name]
        # Combine overlapping/adjacent date ranges
        dates = []
        for event in person_events:
            start = event["start_date"]
            end = event["end_date"]
            if start == end:
                dates.append(start.strftime("%a %b %d"))
            else:
                dates.append(f"{start.strftime('%a %b %d')} - {end.strftime('%a %b %d')}")
        lines.append(f"• {name}: {', '.join(dates)}")

    # Summary stats
    total_person_days = sum(
        (event["end_date"] - event["start_date"]).days + 1
        for event in pto_events
    )
    team_size = len(PTOClient.TEAM_MEMBERS)
    lines.append("")
    lines.append(f"Total: {total_person_days} person-days")
    lines.append(f"Team availability: {team_size - len(by_person)}/{team_size} members")

    return "\n".join(lines)


def main():
    """CLI entry point for PTO client.

    Usage:
        python3 -m sidekick.clients.pto today
        python3 -m sidekick.clients.pto tomorrow
        python3 -m sidekick.clients.pto week
        python3 -m sidekick.clients.pto sprint [days]
        python3 -m sidekick.clients.pto dates START END
    """
    from sidekick.config import get_google_config
    from sidekick.clients.gcalendar import GCalendarClient

    if len(sys.argv) < 2:
        print("Usage: python3 -m sidekick.clients.pto <command>")
        print("\nCommands:")
        print("  today              - PTO today")
        print("  tomorrow           - PTO tomorrow")
        print("  week               - PTO next 7 days")
        print("  sprint [days]      - PTO next N business days (default 10)")
        print("  dates START END    - PTO in date range (YYYY-MM-DD)")
        sys.exit(1)

    try:
        # Initialize clients
        config = get_google_config()
        gcal = GCalendarClient(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            refresh_token=config["refresh_token"]
        )
        pto_client = PTOClient(gcal)

        command = sys.argv[1]

        if command == "today":
            events = pto_client.get_pto_today()
            today = datetime.now().date()
            print(_format_pto_summary(events,
                                     datetime.combine(today, datetime.min.time()),
                                     datetime.combine(today, datetime.min.time())))

        elif command == "tomorrow":
            events = pto_client.get_pto_tomorrow()
            tomorrow = datetime.now().date() + timedelta(days=1)
            print(_format_pto_summary(events,
                                     datetime.combine(tomorrow, datetime.min.time()),
                                     datetime.combine(tomorrow, datetime.min.time())))

        elif command == "week":
            events = pto_client.get_pto_week()
            today = datetime.now().date()
            end = today + timedelta(days=7)
            print(_format_pto_summary(events,
                                     datetime.combine(today, datetime.min.time()),
                                     datetime.combine(end, datetime.min.time())))

        elif command == "sprint":
            sprint_days = 10
            if len(sys.argv) > 2:
                sprint_days = int(sys.argv[2])
            events = pto_client.get_pto_sprint(sprint_days)
            today = datetime.now().date()
            # Calculate end date
            current = today
            business_days_count = 0
            while business_days_count < sprint_days:
                current += timedelta(days=1)
                if current.weekday() < 5:
                    business_days_count += 1
            print(_format_pto_summary(events,
                                     datetime.combine(today, datetime.min.time()),
                                     datetime.combine(current, datetime.min.time())))

        elif command == "dates":
            if len(sys.argv) < 4:
                print("Error: dates command requires START and END dates (YYYY-MM-DD)")
                sys.exit(1)
            start_str = sys.argv[2]
            end_str = sys.argv[3]
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d")
            events = pto_client.get_pto_in_range(start_date, end_date)
            print(_format_pto_summary(events, start_date, end_date))

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

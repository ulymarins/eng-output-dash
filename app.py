"""
Engineering Metrics Dashboard
Run with: streamlit run app.py
Requires: streamlit, PyGithub, pandas, plotly
"""

import os
from datetime import date, timedelta
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st
from github import Auth, Github, GithubException

DEFAULT_ORG = "talon-one"
DEFAULT_TOKEN = os.getenv("GH_DASH_DEFAULT_TOKEN", "")


def search_prs_created(
    gh: Github, org: str, username: str, start_date: date, end_date: date
) -> Dict[str, Any]:
    """Fetch PRs created by the user and compute counts plus additions/deletions."""
    created_count = 0
    merged_count = 0
    additions = 0
    deletions = 0
    created_dates: List[date] = []
    merged_dates: List[date] = []
    pr_details: List[Dict[str, Any]] = []

    query = (
        f"org:{org} author:{username} is:pr "
        f"created:{start_date.isoformat()}..{end_date.isoformat()}"
    )

    for issue in gh.search_issues(query=query, sort="created", order="asc"):
        try:
            pr = issue.as_pull_request()
        except GithubException:
            # Skip if the issue cannot be converted (should be rare).
            continue

        created_count += 1
        if issue.created_at:
            created_dates.append(issue.created_at.date())
        try:
            if pr.is_merged():
                merged_count += 1
                if pr.merged_at:
                    merged_dates.append(pr.merged_at.date())
            additions += pr.additions or 0
            deletions += pr.deletions or 0
            pr_details.append(
                {
                    "username": username,
                    "title": pr.title,
                    "url": pr.html_url,
                    "created_at": pr.created_at,
                    "merged_at": pr.merged_at,
                    "state": pr.state,
                }
            )
        except GithubException:
            # If a PR fetch fails mid-loop, keep moving with collected data.
            continue

    return {
        "prs_created": created_count,
        "prs_merged": merged_count,
        "additions": additions,
        "deletions": deletions,
        "created_dates": created_dates,
        "merged_dates": merged_dates,
        "pr_details": pr_details,
    }


def search_reviews(
    gh: Github, org: str, username: str, start_date: date, end_date: date
) -> Dict[str, Any]:
    """
    Count PRs where the user acted as a reviewer within the org.

    GitHub search supports `reviewed-by:`; using updated as a proxy for review date.
    """
    query = (
        f"org:{org} is:pr reviewed-by:{username} "
        f"updated:{start_date.isoformat()}..{end_date.isoformat()}"
    )
    review_dates: List[date] = []
    review_details: List[Dict[str, Any]] = []
    count = 0

    max_items = 200  # safety cap to avoid excessive API calls
    try:
        for idx, issue in enumerate(
            gh.search_issues(query=query, sort="updated", order="desc")
        ):
            if idx >= max_items:
                break
            try:
                pr = issue.as_pull_request()
                for review in pr.get_reviews():
                    if not review.user:
                        continue
                    if review.user.login.lower() != username.lower():
                        continue
                    if not review.submitted_at:
                        continue
                    submitted_date = review.submitted_at.date()
                    if start_date <= submitted_date <= end_date:
                        count += 1
                        review_dates.append(submitted_date)
                        review_details.append(
                            {
                                "username": username,
                                "pr_title": pr.title,
                                "pr_url": pr.html_url,
                                "submitted_at": review.submitted_at,
                                "state": review.state,
                            }
                        )
            except GithubException:
                continue
    except GithubException:
        count = 0

    # Fallback: iterate PRs updated in range and count reviews explicitly if none found.
    if count == 0:
        fallback_query = (
            f"org:{org} is:pr updated:{start_date.isoformat()}..{end_date.isoformat()}"
        )
        try:
            counted_prs = 0
            for issue in gh.search_issues(
                query=fallback_query, sort="updated", order="desc"
            ):
                if counted_prs >= max_items:
                    break  # avoid excessive API calls
                counted_prs += 1
                try:
                    pr = issue.as_pull_request()
                    for review in pr.get_reviews():
                        if not review.user:
                            continue
                        if review.user.login.lower() != username.lower():
                            continue
                        if not review.submitted_at:
                            continue
                        submitted_date = review.submitted_at.date()
                        if start_date <= submitted_date <= end_date:
                            count += 1
                            review_dates.append(submitted_date)
                            review_details.append(
                                {
                                    "username": username,
                                    "pr_title": pr.title,
                                    "pr_url": pr.html_url,
                                    "submitted_at": review.submitted_at,
                                    "state": review.state,
                                }
                            )
                except GithubException:
                    continue
        except GithubException:
            pass

    return {"count": count, "review_dates": review_dates, "review_details": review_details}


def build_metrics(
    token: str, org: str, users: List[str], start_date: date, end_date: date
) -> Dict[str, pd.DataFrame]:
    gh = Github(auth=Auth.Token(token), per_page=50)
    rows = []
    pr_events: List[Dict[str, Any]] = []
    review_events: List[Dict[str, Any]] = []
    pr_list: List[Dict[str, Any]] = []
    review_list: List[Dict[str, Any]] = []

    for user in users:
        with st.spinner(f"Fetching data for {user}"):
            created_stats = search_prs_created(gh, org, user, start_date, end_date)
            reviews_data = search_reviews(gh, org, user, start_date, end_date)

        prs_created = created_stats["prs_created"]
        prs_merged = created_stats["prs_merged"]
        merge_ratio = (prs_merged / prs_created) * 100 if prs_created else 0

        rows.append(
            {
                "username": user,
                "prs_created": prs_created,
                "prs_merged": prs_merged,
                "merge_ratio_%": round(merge_ratio, 1),
                "reviews": reviews_data["count"],
                "additions": created_stats["additions"],
                "deletions": created_stats["deletions"],
            }
        )

        for d in created_stats["created_dates"]:
            pr_events.append({"username": user, "date": d, "event": "created"})
        for d in created_stats["merged_dates"]:
            pr_events.append({"username": user, "date": d, "event": "merged"})
        for d in reviews_data["review_dates"]:
            review_events.append({"username": user, "date": d})
        pr_list.extend(created_stats["pr_details"])
        review_list.extend(reviews_data["review_details"])

    metrics_df = pd.DataFrame(rows)
    pr_events_df = pd.DataFrame(pr_events)
    review_events_df = pd.DataFrame(review_events)
    pr_list_df = pd.DataFrame(pr_list)
    review_list_df = pd.DataFrame(review_list)
    return {
        "metrics": metrics_df,
        "pr_events": pr_events_df,
        "review_events": review_events_df,
        "pr_list": pr_list_df,
        "review_list": review_list_df,
    }


def main() -> None:
    st.set_page_config(
        page_title="Engineering Metrics Dashboard",
        page_icon="📊",
        layout="wide",
    )

    st.title("Engineering Metrics Dashboard")
    st.write(
        "Analyze pull request and review activity for engineers in a GitHub organization."
    )
    st.warning(
        "Note: Fetch time scales with the number of users and the date range. "
        "Larger queries will take longer."
    )

    st.sidebar.header("Inputs")
    token = st.sidebar.text_input(
        "GitHub Personal Access Token (PAT)",
        type="password",
        help="Required",
        value=DEFAULT_TOKEN,
    )
    org = st.sidebar.text_input(
        "Organization Name", help="Exact org login", value=DEFAULT_ORG
    )
    raw_users = st.sidebar.text_area(
        "Usernames (comma-separated)", placeholder="user1, user2, user3"
    )
    today = date.today()
    default_start = today - timedelta(days=30)
    date_selection = st.sidebar.date_input(
        "Date Range",
        value=(default_start, today),
        help="Start and end dates inclusive",
    )
    if isinstance(date_selection, (list, tuple)) and len(date_selection) == 2:
        start_date, end_date = date_selection
    else:
        # If the widget returns a single date, treat it as both start and end.
        start_date = end_date = date_selection

    analyze = st.sidebar.button("Analyze")

    if analyze:
        if not token or not org or not raw_users:
            st.warning("Please provide a token, organization, and at least one user.")
            return
        if isinstance(start_date, tuple):
            st.warning("Please select a start and end date.")
            return
        if start_date > end_date:
            st.warning("Start date must be on or before end date.")
            return

        users = [u.strip() for u in raw_users.split(",") if u.strip()]
        if not users:
            st.warning("No valid usernames provided.")
            return

        try:
            data = build_metrics(token, org, users, start_date, end_date)
        except GithubException as e:
            st.error(f"GitHub error: {e.data.get('message') if e.data else str(e)}")
            return
        except Exception as e:  # noqa: BLE001
            st.error(f"Unexpected error: {e}")
            return

        df = data["metrics"]
        pr_events_df = data["pr_events"]
        review_events_df = data["review_events"]
        pr_list_df = data["pr_list"]
        review_list_df = data["review_list"]

        if df.empty:
            st.info(
                "No data found for the provided parameters. "
                "If you are querying private repos, ensure the token has `repo` scope. "
                "Also confirm the usernames and date range."
            )
            return

        total_prs = int(df["prs_created"].sum())
        total_reviews = int(df["reviews"].sum())

        kpi1, kpi2 = st.columns(2)
        kpi1.metric("Total PRs Created", f"{total_prs}")
        kpi2.metric("Total Reviews", f"{total_reviews}")

        fig_prs = px.bar(
            df,
            x="username",
            y=["prs_created", "prs_merged"],
            barmode="group",
            title="PR Activity",
            labels={"value": "Count", "username": "User", "variable": "Metric"},
        )
        st.plotly_chart(fig_prs, width="stretch")

        # Time-series charts placed alongside core visuals
        if not pr_events_df.empty:
            pr_events_df["date"] = pd.to_datetime(pr_events_df["date"])
            pr_daily = (
                pr_events_df.groupby(["date", "username", "event"])
                .size()
                .reset_index(name="count")
            )
            fig_pr_time = px.line(
                pr_daily,
                x="date",
                y="count",
                color="username",
                line_dash="event",
                markers=True,
                title="PRs Over Time (Created vs Merged)",
                labels={"count": "PRs", "date": "Date", "username": "User"},
            )
            st.plotly_chart(fig_pr_time, width="stretch")

        if not review_events_df.empty:
            review_events_df["date"] = pd.to_datetime(review_events_df["date"])
            review_daily = (
                review_events_df.groupby(["date", "username"])
                .size()
                .reset_index(name="count")
            )
            fig_review_time = px.line(
                review_daily,
                x="date",
                y="count",
                color="username",
                markers=True,
                title="Reviews Over Time",
                labels={"count": "Reviews", "date": "Date", "username": "User"},
            )
            st.plotly_chart(fig_review_time, width="stretch")

        fig_reviews = px.bar(
            df,
            x="username",
            y="reviews",
            title="Review Activity",
            labels={"reviews": "Reviews", "username": "User"},
        )
        st.plotly_chart(fig_reviews, width="stretch")

        st.subheader("Detailed Metrics")
        st.dataframe(df, width="stretch")

        if total_prs == 0 and total_reviews == 0:
            st.warning(
                "All metrics are zero. Double-check PAT scopes (`repo`, `read:org`), "
                "org login, usernames, and date range. Private repos require `repo`."
            )

        # Raw lists for drill-down
        if not pr_list_df.empty:
            pr_list_df = pr_list_df.copy()
            pr_list_df["created_at"] = pd.to_datetime(pr_list_df["created_at"])
            pr_list_df["merged_at"] = pd.to_datetime(pr_list_df["merged_at"])
            st.subheader("PRs Created (raw)")
            st.caption("Includes title, URL, created, merged; limited to search window.")
            st.dataframe(pr_list_df, width="stretch")

        if not review_list_df.empty:
            review_list_df = review_list_df.copy()
            review_list_df["submitted_at"] = pd.to_datetime(
                review_list_df["submitted_at"]
            )
            st.subheader("Reviews (raw)")
            st.caption(
                "Individual reviews with timestamps; capped to 200 PRs per user to keep fetch time reasonable."
            )
            st.dataframe(review_list_df, width="stretch")

        st.subheader("Debug (for troubleshooting)")
        with st.expander("Show raw metrics dataframe"):
            st.dataframe(df)
    else:
        st.info("Enter inputs in the sidebar and click Analyze to fetch data.")


if __name__ == "__main__":
    main()

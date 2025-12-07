# Engineering Metrics Dashboard

Streamlit app that visualizes GitHub engineering activity (PRs and reviews) for specified users within an organization over a chosen date range. It uses PyGithub for data, pandas for aggregation, and Plotly for interactive charts.

Live demo: https://eng-output-dash-dfz9umftmvkvefz7zovkhz.streamlit.app

## Features
- Sidebar inputs: PAT (password field), organization, usernames (comma-separated), date range, Analyze button.
- Metrics per user: PRs created, PRs merged, merge ratio, reviews, additions, deletions.
- Visuals: KPI totals, grouped bar charts (PRs created vs merged, reviews), time-series for PRs (created/merged) and reviews, sortable detailed table.
- Debug expander to inspect raw metrics dataframe.

## Run locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export GH_DASH_DEFAULT_TOKEN=your_pat_here  # optional; prefill token field
streamlit run app.py
```

## Deploy to Streamlit Community Cloud
- Push `app.py` and `requirements.txt` to your repo.
- In Streamlit Cloud, point to `app.py`.
- Set secrets (e.g., `GH_DASH_DEFAULT_TOKEN`) in the app’s Secrets.

## Notes and disclaimer
- GitHub is a single data source; metrics are incomplete without context (e.g., design, mentoring, on-call, incident response). Do not evaluate people solely by output counts.
- PAT scopes: use `repo` for private data and `read:org` for org info.

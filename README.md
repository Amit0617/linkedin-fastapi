# LinkedIn Profile API

A FastAPI service, structured like [Vercel's FastAPI example](https://github.com/vercel/vercel/tree/main/examples/fastapi), that takes a LinkedIn profile URL and returns a merged JSON document with top-card info, about, experience, and education -- fetched live from LinkedIn and parsed from its internal RSC ("React Server Components") responses.

## Project layout

```
app/
  __init__.py
  api/
    __init__.py
    main.py           <- API router (includes all route modules)
    routes/
      __init__.py
      linkedin.py     <- LinkedIn profile endpoint
  core/
    __init__.py
    config.py         <- settings & env var loading
  main.py             <- FastAPI app factory
  parsers/
    __init__.py
    common.py         <- shared RSC parsing helpers
    experience.py     <- about + experience parsing
    education.py      <- education parsing
    top_card.py       <- name/headline/location from HTML
  services/
    __init__.py
    fetcher.py        <- fetches profile HTML + RSC component payloads
  templates/
    index.html        <- landing page
public/
  favicon.ico
pyproject.toml
.env.example
```

## How it works

1. `POST /api/v1/linkedin/profile` with `{"url": "https://www.linkedin.com/in/<vanity>/"}`.
2. The server:
   - Fetches the plain profile page HTML to pull top-card info (name, headline, location) and LinkedIn's internal member id.
   - Fetches three internal SDUI/RSC component payloads (About, Experience, Education-and-below) the same way the LinkedIn web app does.
   - Parses each payload with the corresponding parser and merges everything into one JSON response.


## Running locally

```bash
uv pip install -r pyproject.toml

cp .env.example .env   # fill in your cookies

uvicorn app.main:app --reload --port 8000
```

Then:

```bash
curl -X POST http://localhost:8000/api/v1/linkedin/profile \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.linkedin.com/in/username/"}'
```

## Response shape

```json
{
  "vanity_name": "...",
  "profile": {
    "full_name": "...",
    "headline": "...",
    "location": "...",
    "profile_canonical_url": "..."
  },
  "about": "...",
  "experiences": [
    {
      "title": "...",
      "company": "...",
      "location": "...",
      "duration": "...",
      "description": "...",
      "employment_type": "..."
    }
  ],
  "education": [
    {
      "school": "...",
      "degree": "...",
      "field_of_study": "...",
      "duration": "...",
      "grade": "...",
      "activities_and_societies": "..."
    }
  ]
}
```

## Caveats

- This scrapes LinkedIn's private, undocumented internal API. It can break at any time if LinkedIn changes their markup, component ids, or anti-bot measures, and heavy use risks the logged-in account being rate-limited or flagged.
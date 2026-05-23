# Google Maps Public Evidence

NexusIntel does not infer Google Maps identity from an email address and does not use internal Google APIs.

Supported workflow:

1. Analyst creates or selects a `google_maps_profile` or `url` entity with a public Google Maps contribution/profile URL.
2. Run `maps_profile_to_reviews` from the Transform Library.
3. The adapter fetches the public document if accessible and stores the raw HTML/metadata in the evidence vault.
4. Visible public profile metadata, review snippets, photo URLs, and place URLs are converted into graph artifacts only when present in the public document.

Analyst-provided screenshots or exported text should be imported as evidence and marked `analyst_provided` until independently fetched.

Disallowed:

- Private Google user data.
- Internal Google APIs.
- Email-to-Gaia inference.
- Authenticated scraping.

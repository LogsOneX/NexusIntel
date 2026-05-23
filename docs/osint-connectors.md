# OSINT Connectors

Connector keys are optional and configured in Settings or environment variables. Core DNS/RDAP/Gravatar/profile parsing works without paid subscriptions.

Supported BYOK names:

- `GITHUB_TOKEN` for official GitHub public search.
- `HIBP_API_KEY` for official Have I Been Pwned breached-account API.
- `URLSCAN_API_KEY` reserved for URLScan connector.
- `GOOGLE_MAPS_API_KEY` for analyst-supplied place enrichment only, not private profile inference.
- `SHODAN_API_KEY`, `CENSYS_API_KEY`, `VIRUSTOTAL_API_KEY` reserved for official connector modules.
- `TWILIO_LOOKUP_API_KEY`, `NUMVERIFY_API_KEY` reserved for lawful phone lookup providers.

A disabled transform is intentional. It means the connector is missing, the adapter is not implemented yet, or the selected node type is not valid input.

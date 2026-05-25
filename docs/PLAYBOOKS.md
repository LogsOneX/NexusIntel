# Playbooks

NexusIntel playbooks turn repeatable OSINT workflows into safe analyst plans. They do not auto-run risky or broad actions without analyst confirmation.

## Included Playbooks

- `email_investigation`
- `username_investigation`
- `domain_impersonation`
- `phone_investigation`
- `crypto_wallet_investigation`
- `website_clone_detection`
- `threat_actor_infrastructure_mapping`
- `report_preparation`

## API

- `GET /api/v1/playbooks`
- `POST /api/v1/investigations/{id}/playbooks/{playbook_id}/plan`
- `POST /api/v1/investigations/{id}/playbooks/{playbook_id}/run`

`run` currently returns a safe execution plan and queued steps. Transform dispatch remains an explicit analyst action.

from __future__ import annotations

from backend.osint.types import AdapterResult, EntityInput, OSINTAdapter, RateLimitProfile, RunContext


class BaseAdapter(OSINTAdapter):
    id = "base"
    name = "Base Adapter"
    description = "Base adapter"
    input_types: list[str] = []
    output_types: list[str] = []
    requires_api_key = False
    passive = True
    legal_note = "Passive public-source collection only."
    rate_limit = RateLimitProfile()

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        return AdapterResult(adapter_id=self.id, input=entity, warnings=["Adapter has no implementation"], status="skipped")

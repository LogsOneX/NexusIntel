import re

from app.osint.schema import FindingBatch, entity, relationship


class PhoneRecon:
    name = "phone_recon"

    async def run(self, target: str, target_type: str, mode: str) -> FindingBatch:
        if target_type != "phone":
            return FindingBatch(self.name, "No phone number target available.")
        digits = re.sub(r"\D", "", target)
        normalized = f"+{digits}" if target.strip().startswith("+") else digits
        phone = entity("phone", normalized, normalized, 90, self.name)
        entities = [phone]
        relationships = []

        hints = []
        if digits.startswith("62"):
            hints.append(("Country code +62 Indonesia", "country_hint", 72))
        elif digits.startswith("1"):
            hints.append(("Country code +1 NANP", "country_hint", 65))
        elif digits.startswith("44"):
            hints.append(("Country code +44 United Kingdom", "country_hint", 65))
        if len(digits) < 8:
            hints.append(("Number is unusually short", "risk", 70))
        if len(digits) > 15:
            hints.append(("Number exceeds E.164 max length", "risk", 82))

        for label, type_, confidence in hints:
            node = entity(type_, f"{normalized}:{label}", label, confidence, self.name)
            entities.append(node)
            relationships.append(relationship(phone, node, "has_hint", "Has Hint", confidence))

        return FindingBatch(
            self.name,
            "Performed offline phone normalization and country-code hinting.",
            entities,
            relationships,
            {"digits": digits, "mode": mode},
        )

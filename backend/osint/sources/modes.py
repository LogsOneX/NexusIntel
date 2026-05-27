from __future__ import annotations

from enum import StrEnum

class SourceMode(StrEnum):
    LOCAL_NATIVE = "LOCAL_NATIVE"
    PUBLIC_PASSIVE = "PUBLIC_PASSIVE"
    BROWSER_ASSISTED = "BROWSER_ASSISTED"
    IMPORTED_EVIDENCE = "IMPORTED_EVIDENCE"
    OPTIONAL_BYOK = "OPTIONAL_BYOK"

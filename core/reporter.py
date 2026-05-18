import os
import json
from datetime import datetime
from typing import Dict, Any

class ReportGenerator:
    def __init__(self, target: str, results: Dict[str, Any], output_dir: str = "results"):
        self.target = target
        self.results = results
        self.output_dir = output_dir
        self.timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.safe_target = target.replace("http://", "").replace("https://", "").replace("/", "_")
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_json(self) -> str:
        """Compiles standard structure for machine-readable analytical pipelines."""
        payload = {
            "meta": {
                "target": self.target,
                "generated_at": self.timestamp,
                "total_modules": len(self.results)
            },
            "data": self.results
        }
        
        filepath = os.path.join(self.output_dir, f"report_{self.safe_target}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
        return filepath

    def generate_markdown(self) -> str:
        """Generates clear, executive executive summaries and data tables."""
        filepath = os.path.join(self.output_dir, f"report_{self.safe_target}.md")
        
        md_content = f"""# Public Data Aggregator & Analytics Report
**Target:** `{self.target}`  
**Generated At:** {self.timestamp}  

---

## 1. Executive Summary
The framework successfully executed analytics checks against the specified target descriptor. Individual modular data points have been collected below.

| Module Name | Execution Status | Data Items Found |
| :--- | :--- | :--- |
"""
        # Append summary table metadata dynamically
        for mod_name, mod_data in self.results.items():
            status = "SUCCESS" if mod_data.get("status") != "error" else "FAILED"
            count = len(mod_data.get("data", {})) if isinstance(mod_data.get("data"), dict) else len(mod_data.get("data", []))
            md_content += f"| {mod_name} | {status} | {count} entries |\n"

        md_content += "\n## 2. Detailed Module Breakdown\n"

        for mod_name, mod_data in self.results.items():
            md_content += f"### Module: {mod_name.replace('_', ' ').title()}\n"
            if mod_data.get("status") == "error":
                md_content += f"> **Error Encountered:** {mod_data.get('message')}\n\n"
                continue

            data = mod_data.get("data", {})
            if isinstance(data, dict) and data:
                md_content += "| Metric / Field | Value |\n| :--- | :--- |\n"
                for k, v in data.items():
                    md_content += f"| **{k}** | {v} |\n"
                md_content += "\n"
            elif isinstance(data, list) and data:
                for item in data:
                    md_content += f"- {item}\n"
                md_content += "\n"
            else:
                md_content += "*No public profile data extracted or available.*\n\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        return filepath

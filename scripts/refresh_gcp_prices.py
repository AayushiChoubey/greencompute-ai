#!/usr/bin/env python3
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal

PROJECT_ID = "greencompute-ai"
LOCATION = "asia-south1"
SECRET_NAME = "greencompute-pricing-api-key"
OUTPUT_FILE = "tmp/current_machine_prices.ndjson"

SQL = """
SELECT DISTINCT
  m.region,
  m.machine_type,
  m.provisioning_model,
  m.component_type,
  m.sku_id,
  m.sku_display_name,
  p.vcpu_count,
  p.memory_gb
FROM `greencompute_config.pricing_sku_mappings` AS m
JOIN `greencompute_config.machine_profiles` AS p
  ON m.cloud_provider = p.cloud_provider
  AND m.machine_type = p.machine_type
WHERE m.active = TRUE
  AND p.active = TRUE
ORDER BY m.region, m.machine_type, m.provisioning_model, m.component_type
"""

def run(command):
    return subprocess.check_output(command, text=True).strip()

def get_api_key():
    return run([
        "gcloud", "secrets", "versions", "access", "latest",
        f"--secret={SECRET_NAME}",
        f"--project={PROJECT_ID}",
    ])

def get_rows():
    output = run([
        "bq", f"--location={LOCATION}", "query",
        "--use_legacy_sql=false",
        "--max_rows=1000",
        "--format=json",
        SQL,
    ])
    return json.loads(output)

def get_sku_price(api_key, sku_id):
    query = urllib.parse.urlencode({
        "key": api_key,
        "currencyCode": "USD",
    })
    url = f"https://cloudbilling.googleapis.com/v1beta/skus/{sku_id}/price?{query}"

    with urllib.request.urlopen(url) as response:
        payload = json.load(response)

    if "error" in payload:
        raise RuntimeError(f"{sku_id}: {payload['error']}")

    tier = payload["rate"]["tiers"][0]["listPrice"]
    units = Decimal(str(tier.get("units", "0")))
    nanos = Decimal(str(tier.get("nanos", 0))) / Decimal("1000000000")
    return units + nanos, payload

def main():
    api_key = get_api_key()
    mappings = get_rows()

    component_price_cache = {}
    candidates = {}

    for row in mappings:
        sku_id = row["sku_id"]

        if sku_id not in component_price_cache:
            component_price_cache[sku_id] = get_sku_price(api_key, sku_id)

        component_price, raw_api_response = component_price_cache[sku_id]

        key = (
            row["region"],
            row["machine_type"],
            row["provisioning_model"],
        )

        if key not in candidates:
            candidates[key] = {
                "vcpu_count": Decimal(str(row["vcpu_count"])),
                "memory_gb": Decimal(str(row["memory_gb"])),
                "components": {},
            }

        candidates[key]["components"][row["component_type"]] = {
            "sku_id": sku_id,
            "display_name": row["sku_display_name"],
            "price_per_hour": component_price,
            "raw_api_response": raw_api_response,
        }

    observed_at = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp_text = observed_at.isoformat().replace("+00:00", "Z")
    id_timestamp = observed_at.strftime("%Y%m%dT%H%M%SZ")
    output_rows = []

    for (region, machine_type, provisioning_model), candidate in candidates.items():
        components = candidate["components"]

        if "VCPU" not in components or "MEMORY_GB" not in components:
            raise RuntimeError(
                f"Missing CPU or memory price for "
                f"{region} / {machine_type} / {provisioning_model}"
            )

        cpu_total = candidate["vcpu_count"] * components["VCPU"]["price_per_hour"]
        memory_total = candidate["memory_gb"] * components["MEMORY_GB"]["price_per_hour"]
        total_price = cpu_total + memory_total

        output_rows.append({
            "price_observation_id": (
                f"gcp-public-{region}-{machine_type}-{provisioning_model.lower()}-{id_timestamp}"
            ),
            "cloud_provider": "GCP",
            "region": region,
            "machine_type": machine_type,
            "provisioning_model": provisioning_model,
            "operating_system": "LINUX",
            "currency_code": "USD",
            "billing_unit": "HOUR",
            "price_per_unit": float(total_price),
            "observed_at": timestamp_text,
            "effective_from": None,
            "effective_to": None,
            "source_name": "GCP_PRICING_API",
            "source_version": "v1beta",
            "is_synthetic": False,
            "raw_source_payload": {
                "calculation": "(vCPU count × CPU hourly price) + (memory GB × memory hourly price)",
                "cpu_component": {
                    "sku_id": components["VCPU"]["sku_id"],
                    "price_per_hour_usd": str(components["VCPU"]["price_per_hour"]),
                },
                "memory_component": {
                    "sku_id": components["MEMORY_GB"]["sku_id"],
                    "price_per_hour_usd": str(components["MEMORY_GB"]["price_per_hour"]),
                },
            },
            "ingested_at": timestamp_text,
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as output:
        for row in output_rows:
            output.write(json.dumps(row) + "\n")

    run([
        "bq", f"--location={LOCATION}", "load",
        "--source_format=NEWLINE_DELIMITED_JSON",
        "greencompute_metrics.price_observations",
        OUTPUT_FILE,
    ])

    print(f"Loaded {len(output_rows)} real machine-price observations.")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"PRICE REFRESH FAILED: {error}", file=sys.stderr)
        sys.exit(1)

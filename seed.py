"""Load synthetic Patient + Observations into HAPI FHIR (no auth, direct to HAPI)."""

import httpx
import sys

HAPI_DIRECT = "http://localhost:8084"

PATIENT = {
    "resourceType": "Patient",
    "id": "example",
    "name": [{"family": "Smith", "given": ["Jane"]}],
    "gender": "female",
    "birthDate": "1985-07-14",
}

OBSERVATIONS = [
    {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}],
        },
        "subject": {"reference": "Patient/example"},
        "effectiveDateTime": "2026-10-01",
        "valueQuantity": {"value": 6.1, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
    },
    {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}],
        },
        "subject": {"reference": "Patient/example"},
        "effectiveDateTime": "2026-07-01",
        "valueQuantity": {"value": 6.4, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
    },
    {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "2339-0", "display": "Glucose"}],
        },
        "subject": {"reference": "Patient/example"},
        "effectiveDateTime": "2026-10-01",
        "valueQuantity": {"value": 95, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
    },
]


def main():
    client = httpx.Client(base_url=HAPI_DIRECT, timeout=30.0)

    print("Seeding Patient...")
    resp = client.put("/fhir/Patient/example", json=PATIENT,
                      headers={"Content-Type": "application/fhir+json"})
    print(f"  Patient/example: {resp.status_code}")
    if resp.status_code >= 400:
        print(f"  Error: {resp.text[:200]}")
        sys.exit(1)

    print("Seeding Observations...")
    for i, obs in enumerate(OBSERVATIONS):
        resp = client.post("/fhir/Observation", json=obs,
                           headers={"Content-Type": "application/fhir+json"})
        display = obs["code"]["coding"][0]["display"]
        print(f"  Observation {i+1} ({display}): {resp.status_code}")
        if resp.status_code >= 400:
            print(f"  Error: {resp.text[:200]}")

    print("Done. Seeded 1 Patient and 3 Observations.")


if __name__ == "__main__":
    main()

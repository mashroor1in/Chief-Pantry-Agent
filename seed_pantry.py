import os
from google.cloud import firestore

# HARDCODED PROJECT ID string (do NOT use os.getenv("GOOGLE_CLOUD_PROJECT") or google.auth.default())
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-87211ecaf6a5"

def seed_pantry():
    print(f"Connecting to Firestore for project '{FIRESTORE_PROJECT_ID}'...")
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    pantry_ref = db.collection("pantry_items")

    initial_items = [
        {
            "id": "item_001",
            "name": "Extra Virgin Olive Oil",
            "category": "Oils & Condiments",
            "quantity": 1.0,
            "unit": "bottle",
            "expiration_date": "2027-01-15",
            "dietary_tags": ["vegan", "keto", "gluten-free"]
        },
        {
            "id": "item_002",
            "name": "Boneless Chicken Breast",
            "category": "Proteins",
            "quantity": 500.0,
            "unit": "grams",
            "expiration_date": "2026-10-05",
            "dietary_tags": ["keto", "gluten-free", "high-protein"]
        },
        {
            "id": "item_003",
            "name": "Fresh Garlic Bulbs",
            "category": "Produce",
            "quantity": 3.0,
            "unit": "bulbs",
            "expiration_date": "2026-10-20",
            "dietary_tags": ["vegan", "keto", "gluten-free"]
        },
        {
            "id": "item_004",
            "name": "Organic Jasmine Rice",
            "category": "Grains & Pasta",
            "quantity": 1.0,
            "unit": "kg",
            "expiration_date": "2027-06-30",
            "dietary_tags": ["vegan", "gluten-free"]
        },
        {
            "id": "item_005",
            "name": "Hass Avocados",
            "category": "Produce",
            "quantity": 4.0,
            "unit": "pieces",
            "expiration_date": "2026-10-02",
            "dietary_tags": ["vegan", "keto", "gluten-free"]
        }
    ]

    for item in initial_items:
        doc_ref = pantry_ref.document(item["id"])
        doc_ref.set(item)
        print(f"Seeded pantry item: {item['name']} ({item['quantity']} {item['unit']})")

    print(f"Successfully seeded {len(initial_items)} pantry items into Firestore!")

if __name__ == "__main__":
    seed_pantry()

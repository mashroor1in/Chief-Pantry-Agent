# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os

from pathlib import Path
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback

# HARDCODED PROJECT ID string (do NOT use os.getenv("GOOGLE_CLOUD_PROJECT") or google.auth.default())
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-87211ecaf6a5"

# HARDCODED Cloud Storage Bucket Name
GCS_BUCKET_NAME = "pantry-chef-images-qwiklabs-gcp-02-87211ecaf6a5"

# Load Agent Engine resource name from deployment_metadata.json if available
deployment_metadata_path = (
    Path(__file__).resolve().parent.parent / "deployment_metadata.json"
)
agent_engine_resource_name = None
MEMORY_BANK_ID = "4642074320795860992"

if deployment_metadata_path.exists():
    try:
        with open(deployment_metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            agent_engine_resource_name = meta.get("remote_agent_runtime_id")
            if agent_engine_resource_name:
                MEMORY_BANK_ID = agent_engine_resource_name.split("/")[-1]
    except Exception as e:
        print(f"Warning: Could not load deployment_metadata.json: {e}")

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each agent turn, send the session events to Memory Bank for fact and allergy extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory extraction skipped: {e}")
    return None


def memory_bank_service_builder():
    """Memory service builder for Agent Runtime deployment."""
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


NUTRITION_DATABASE = {
    "chicken": {"calories": 1.65, "protein": 0.31, "carbs": 0.0, "fat": 0.036},  # per gram
    "rice": {"calories": 1.30, "protein": 0.027, "carbs": 0.28, "fat": 0.003},  # per gram
    "olive oil": {"calories": 119.0, "protein": 0.0, "carbs": 0.0, "fat": 13.5},  # per tbsp
    "oil": {"calories": 119.0, "protein": 0.0, "carbs": 0.0, "fat": 13.5},
    "avocado": {"calories": 160.0, "protein": 2.0, "carbs": 8.5, "fat": 14.7},  # per piece
    "egg": {"calories": 72.0, "protein": 6.3, "carbs": 0.4, "fat": 4.8},  # per piece
    "eggs": {"calories": 72.0, "protein": 6.3, "carbs": 0.4, "fat": 4.8},
    "garlic": {"calories": 5.0, "protein": 0.2, "carbs": 1.0, "fat": 0.0},  # per clove
}


def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def check_pantry(query: str = "") -> str:
    """Reads items from the pantry collection in Firestore.

    Args:
        query: Optional string to filter pantry items by name, category, or dietary tags.

    Returns:
        A summary string listing all matching pantry items with quantity, unit, and details.
    """
    try:
        db = get_firestore_client()
        docs = db.collection("pantry_items").stream()
        items = []
        for doc in docs:
            data = doc.to_dict()
            items.append(data)

        if not items:
            return "Your pantry is currently empty."

        if query:
            q_lower = query.lower()
            filtered = [
                item
                for item in items
                if q_lower in item.get("name", "").lower()
                or q_lower in item.get("category", "").lower()
                or any(q_lower in tag.lower() for tag in item.get("dietary_tags", []))
            ]
            if not filtered:
                return f"No pantry items matching '{query}' were found."
            items = filtered

        lines = ["Here are the items in your pantry:"]
        for item in items:
            tags = ", ".join(item.get("dietary_tags", []))
            tags_str = f" [Tags: {tags}]" if tags else ""
            lines.append(
                f"- {item.get('name')}: {item.get('quantity')} {item.get('unit')} (Category: {item.get('category')}){tags_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading pantry items from Firestore: {e}"


def add_pantry_item(
    name: str, category: str, quantity: float, unit: str, dietary_tags: str = ""
) -> str:
    """Adds a new item or updates an existing item in the Firestore pantry collection.

    Args:
        name: Name of the ingredient/item (e.g. 'Avocado', 'Olive Oil').
        category: Food category (e.g. 'Produce', 'Proteins', 'Oils & Condiments', 'Grains & Pasta').
        quantity: Numerical quantity (e.g. 2.0, 500.0).
        unit: Unit of measure (e.g. 'pieces', 'grams', 'bottles', 'kg').
        dietary_tags: Optional comma-separated dietary tags (e.g. 'vegan, keto, gluten-free').

    Returns:
        Confirmation message detailing the saved pantry item.
    """
    try:
        db = get_firestore_client()
        pantry_ref = db.collection("pantry_items")

        # Check if item with matching name exists
        existing_docs = pantry_ref.where("name", "==", name).limit(1).get()
        doc_id = None
        if existing_docs:
            doc_id = existing_docs[0].id

        if not doc_id:
            doc_id = f"item_{uuid.uuid4().hex[:8]}"

        tags_list = (
            [t.strip().lower() for t in dietary_tags.split(",") if t.strip()]
            if dietary_tags
            else []
        )

        item_data = {
            "id": doc_id,
            "name": name,
            "category": category,
            "quantity": float(quantity),
            "unit": unit,
            "dietary_tags": tags_list,
        }

        pantry_ref.document(doc_id).set(item_data)
        return f"Successfully added/updated pantry item '{name}' ({quantity} {unit}) in Firestore."
    except Exception as e:
        return f"Error adding pantry item to Firestore: {e}"


def calculate_recipe_nutrition(ingredients: str, servings: int = 1) -> str:
    """Calculates estimated caloric and macro nutritional breakdown for a list of recipe ingredients.

    Args:
        ingredients: Comma-separated list of ingredients with quantities (e.g. '200g chicken breast, 1 tbsp olive oil, 2 eggs').
        servings: Number of servings to divide totals by (default 1).

    Returns:
        A formatted summary string with calculated calories, protein, carbs, and fat per serving.
    """
    if servings < 1:
        servings = 1

    total_cal = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    items = [i.strip() for i in ingredients.split(",") if i.strip()]
    parsed_summary = []

    for item in items:
        digits = [
            float(s)
            for s in item.replace("g", " ").split()
            if s.replace(".", "", 1).isdigit()
        ]
        qty = digits[0] if digits else 1.0

        item_lower = item.lower()
        matched = False
        for key, macros in NUTRITION_DATABASE.items():
            if key in item_lower:
                total_cal += macros["calories"] * qty
                total_protein += macros["protein"] * qty
                total_carbs += macros["carbs"] * qty
                total_fat += macros["fat"] * qty
                parsed_summary.append(
                    f"- {item}: ~{round(macros['calories'] * qty)} kcal"
                )
                matched = True
                break

        if not matched:
            total_cal += 50.0 * qty
            total_protein += 2.0 * qty
            total_carbs += 5.0 * qty
            total_fat += 1.0 * qty
            parsed_summary.append(f"- {item}: ~{round(50.0 * qty)} kcal (estimated)")

    per_serving_cal = round(total_cal / servings, 1)
    per_serving_protein = round(total_protein / servings, 1)
    per_serving_carbs = round(total_carbs / servings, 1)
    per_serving_fat = round(total_fat / servings, 1)

    result = [
        f"Nutritional Breakdown ({servings} serving(s)):",
        *parsed_summary,
        f"\nPer Serving ({servings} serving(s) total):",
        f"• Calories: {per_serving_cal} kcal",
        f"• Protein: {per_serving_protein} g",
        f"• Carbohydrates: {per_serving_carbs} g",
        f"• Fat: {per_serving_fat} g",
    ]
    return "\n".join(result)


def search_online_recipes(query: str) -> str:
    """Searches a public recipe database (TheMealDB) for real online recipes matching a query ingredient or meal name.

    Args:
        query: Search term (e.g. 'chicken', 'pasta', 'arrabiata', 'curry').

    Returns:
        A formatted string listing real recipes with category, origin, ingredients, and step instructions.
    """
    api_key = os.getenv("THEMEALDB_API_KEY", "1")
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={encoded_query}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "PantryChefAgent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                return f"API returned HTTP status code {response.status}."
            data = json.loads(response.read().decode("utf-8"))

        meals = data.get("meals")
        if not meals:
            filter_url = f"https://www.themealdb.com/api/json/v1/{api_key}/filter.php?i={encoded_query}"
            req_f = urllib.request.Request(
                filter_url, headers={"User-Agent": "PantryChefAgent/1.0"}
            )
            with urllib.request.urlopen(req_f, timeout=10) as res_f:
                filter_data = json.loads(res_f.read().decode("utf-8"))
            meals = filter_data.get("meals")
            if not meals:
                return f"No online recipes found matching '{query}'."

        results = [f"Found online recipes for '{query}':"]
        for meal in meals[:3]:
            name = meal.get("strMeal")
            category = meal.get("strCategory", "General")
            area = meal.get("strArea", "International")
            instructions = meal.get("strInstructions", "")

            ingredients = []
            for i in range(1, 21):
                ing = meal.get(f"strIngredient{i}")
                meas = meal.get(f"strMeasure{i}")
                if ing and ing.strip():
                    measure_str = f" ({meas.strip()})" if meas and meas.strip() else ""
                    ingredients.append(f"{ing.strip()}{measure_str}")

            ing_summary = (
                ", ".join(ingredients[:8])
                if ingredients
                else "Ingredients listed in steps"
            )
            instr_summary = (
                (instructions[:200] + "...")
                if len(instructions) > 200
                else instructions
            )

            lines = [
                f"\n🍲 **{name}** ({category} - {area})",
                f"• Ingredients: {ing_summary}",
            ]
            if instr_summary:
                lines.append(f"• Instructions: {instr_summary}")
            results.append("\n".join(lines))

        return "\n".join(results)
    except Exception as e:
        return f"Error fetching online recipes from public API: {e}"


def generate_dish_image(dish_name: str, tool_context: ToolContext) -> str:
    """Generates a high-quality preview image of a dish using gemini-3.1-flash-lite-image in the global region,
    saves it as an artifact in Playground, and uploads the image bytes directly to public Cloud Storage.

    Args:
        dish_name: Name or description of the dish/recipe (e.g. 'Chicken Alfredo', 'Avocado Toast').

    Returns:
        The public HTTPS URL of the generated dish image stored in Cloud Storage.
    """
    try:
        genai_client = genai.Client(
            vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
        )
        prompt = f"A delicious, appetizing, professionally photographed plated dish of {dish_name}, vibrant food photography style."

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )

        image_bytes = None
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    break

        if not image_bytes:
            return f"Failed to generate image for '{dish_name}'."

        filename = f"dish_{uuid.uuid4().hex[:8]}.jpg"

        # 1. Save artifact to ToolContext for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes directly to public GCS bucket (no local file writing)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        object_name = f"dishes/{filename}"
        blob = bucket.blob(object_name)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"
        return public_url
    except Exception as e:
        return f"Error generating dish image for '{dish_name}': {e}"


def generate_recipe_video(item_name: str, tool_context: ToolContext) -> str:
    """Generates a short cooking video for an item in the Pantry Chef domain using Google's Omni model (gemini-omni-flash-preview)
    in the global region, saves it as an artifact in Playground, and uploads the video bytes directly to public Cloud Storage.

    Args:
        item_name: Name of the dish, recipe, or cooking technique (e.g. 'Sizzling Garlic Pasta', 'Chopping Basil').

    Returns:
        The public HTTPS URL of the generated video stored in Cloud Storage.
    """
    try:
        genai_client = genai.Client(
            vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
        )
        prompt = f"A short 3-second cooking demonstration video of {item_name}"

        response = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
            response_modalities=["text", "video"],
        )

        if not response or not hasattr(response, "output_video") or not response.output_video:
            return f"Failed to generate video for '{item_name}'."

        raw_data = response.output_video.data
        if isinstance(raw_data, str):
            video_bytes = base64.b64decode(raw_data)
        else:
            video_bytes = raw_data

        if not video_bytes:
            return f"Failed to extract video bytes for '{item_name}'."

        filename = f"video_{uuid.uuid4().hex[:8]}.mp4"

        # 1. Save artifact to ToolContext for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes directly to public GCS bucket (no local file writing)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        object_name = f"videos/{filename}"
        blob = bucket.blob(object_name)
        blob.upload_from_string(video_bytes, content_type="video/mp4")

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"
        return public_url
    except Exception as e:
        return f"Error generating video for '{item_name}': {e}"


# Build A2UI System Prompt using A2uiSchemaManager version 0.8 & BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are a Smart Pantry & Personal Chef Agent. Your mission is to help users manage their pantry "
        "and craft healthy meals based on real recipes, nutritional calculations, and visual dish previews."
    ),
    workflow_description=(
        "Analyze the user's request and return structured UI when appropriate.\n\n"
        "MEMORY & ALLERGY SAFETY RULES:\n"
        "- You remember all user dietary preferences, food allergies (e.g. peanuts, tree nuts, dairy, gluten, shellfish, soy, eggs), "
        "and health restrictions across conversations using Memory Bank (`PreloadMemoryTool`).\n"
        "- Whenever the user mentions any food allergy or dietary intolerance in conversation, acknowledge it and ensure it is saved to memory.\n"
        "- ALWAYS cross-check all recommended recipes, pantry items, and meal plans against the user's remembered allergies. "
        "NEVER suggest a meal containing a user allergen without explicitly warning the user and providing safe substitutes.\n\n"
        "WORKFLOW GUIDELINES:\n"
        "1. When the user asks what to cook or wants meal ideas:\n"
        "   a) Check preloaded memories for any user allergies or dietary restrictions.\n"
        "   b) Call `check_pantry` to view the user's current ingredients stored in Firestore.\n"
        "   c) Call `search_online_recipes` using available pantry items or requested dish names to find real recipes.\n"
        "   d) Call `calculate_recipe_nutrition` to compute total calories and macros for the recommended meal.\n"
        "   e) Call `generate_dish_image` to generate a visual preview image of the suggested dish.\n"
        "   f) Present a clean summary containing available vs required ingredients, step instructions, nutrition, dish image URL, "
        "and an explicit Allergy & Safety Check section.\n"
        "2. When the user mentions buying or using up groceries, call `add_pantry_item` to keep Firestore updated.\n"
        "3. Always offer helpful culinary advice aligned with dietary preferences (e.g., vegan, keto, gluten-free)."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        check_pantry,
        add_pantry_item,
        calculate_recipe_nutrition,
        search_online_recipes,
        generate_dish_image,
        generate_recipe_video,
        PreloadMemoryTool(),
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
    code_executor=code_executor,
)

app = App(
    root_agent=root_agent,
    name="app",
)

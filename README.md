# 👨‍🍳 Pantry Chef Agent

An intelligent, AI-powered Smart Pantry & Personal Chef agent built with **Google ADK (Agent Development Kit)**, **Gemini 2.5 Flash**, **Vertex AI Memory Bank**, **Firestore**, **Imagen 3**, **Gemini Omni**, and **A2UI**.

Pantry Chef manages your pantry inventory, remembers dietary preferences and food allergies across sessions, generates step-by-step recipes with nutrition scaling, and synthesizes visual dish previews and video clips.

![Pantry Chef Demo](assets/demo.gif)

---

## 🚀 Key Features & Capabilities

- **🧠 Memory Bank & Allergy Safety**: Remembers user dietary preferences, food allergies (e.g., peanuts, gluten, dairy), and health goals across sessions using **Vertex AI Memory Bank Service** (`PreloadMemoryTool`). Automatically screens recommended meals against remembered allergies.
- **📦 Pantry Inventory Management**: Tracks real-time ingredient stock (add, check, update) stored in a **Google Cloud Firestore** database (`pantry_items` collection).
- **🍝 Online Recipe Discovery**: Searches real-world recipe databases via **TheMealDB API** based on available pantry items or dish requests.
- **📊 Macro & Nutrition Scaling**: Calculates total calories, protein, carbs, and fat scaled to target serving sizes.
- **🎨 Visual Dish Generation**: Synthesizes high-resolution dish preview images using **Imagen 3** (`imagen-3.0-generate-002`) hosted publicly on **Google Cloud Storage**.
- **🎥 Culinary Video Generation**: Generates 3-second cooking demonstration video clips using **Gemini Omni** (`gemini-omni-flash-preview` in the global location) uploaded directly to Cloud Storage and registered as Playground artifacts.
- **🖥️ Rich Dialogue & A2UI Surface**: Uses **A2UI v0.8** schema rendering structured card surfaces, paired with a modern dark-mode chat UI supporting Markdown rich text rendering.

---

## 🛠️ Architecture & Tech Stack

| Component | Technology / Service |
| :--- | :--- |
| **Agent Framework** | Google ADK (`google.adk.agents.Agent`, Python) |
| **Primary LLM** | Gemini 2.5 Flash (`gemini-2.5-flash`) |
| **Memory Bank** | Vertex AI Memory Bank (`VertexAiMemoryBankService`) |
| **Database** | Google Cloud Firestore (`pantry_items` collection) |
| **Object Storage** | Google Cloud Storage (Public bucket for images & videos) |
| **Image Generation** | Vertex AI Imagen 3 (`imagen-3.0-generate-002`) |
| **Video Generation** | Vertex AI Gemini Omni (`gemini-omni-flash-preview`, `global` location) |
| **Structured UI** | A2UI (Agent-to-User Interface v0.8) & `marked.js` |
| **Frontend Web App** | FastAPI Python Server + Vanilla HTML5/CSS3/JS |

---

## 🛠️ Tools Implementation Summary

The agent's toolset in `app/agent.py` includes:

1. `check_pantry()`: Queries Firestore for stored pantry ingredients and quantities.
2. `add_pantry_item(item_name, quantity, unit)`: Adds or updates pantry items in Firestore.
3. `search_online_recipes(query)`: Retrieves matching recipes and instructions via TheMealDB API.
4. `calculate_recipe_nutrition(dish_name, servings)`: Computes scaled calories and macro breakdowns.
5. `generate_dish_image(dish_name)`: Generates dish image using Imagen 3 and uploads to GCS.
6. `generate_recipe_video(item_name)`: Generates short cooking video using Gemini Omni and uploads to GCS.
7. `PreloadMemoryTool()`: Injects remembered user allergies and dietary preferences into context.

---

## 💻 Local Setup & Development Instructions

### Prerequisites
- Python 3.10+
- `uv` package manager (or standard Python `venv`)
- Google Cloud SDK (`gcloud`) authenticated with a project containing Vertex AI, Firestore, and Cloud Storage permissions.

### Environment Setup

1. **Clone repository and install dependencies**:
   ```bash
   uv sync
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and configure your GCP project and Cloud Storage bucket:
   ```bash
   export GOOGLE_CLOUD_PROJECT="<YOUR_GCP_PROJECT_ID>"
   export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_NUMBER>/locations/us-east1/reasoningEngines/<REASONING_ENGINE_ID>"
   export AGENT_DIRECTORY="app"
   ```

3. **Seed Firestore Pantry Data** *(Optional)*:
   ```bash
   uv run python seed_pantry.py
   ```

### Running the Frontend Server Locally

Start the local web application server:
```bash
uv run python frontend/main.py
```
Open a browser and navigate to the local server port displayed in your terminal logs (default: port `8080`).

---

## 🚀 Deployment

### Deploy Agent to Vertex AI Reasoning Engine
Deploy the agent backend using the Google Agents CLI:
```bash
agents-cli deploy --no-confirm-project --project <YOUR_GCP_PROJECT_ID>
```

### Deploy Frontend Web App to Cloud Run
Build and deploy the web frontend container to Google Cloud Run:
```bash
gcloud run deploy pantry-chef-frontend \
  --source ./frontend \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<YOUR_AGENT_ENGINE_RESOURCE_NAME>",AGENT_DIRECTORY="app"
```

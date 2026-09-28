# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.cli.service_registry import get_service_registry
from google.adk.memory import VertexAiMemoryBankService

MEMORY_BANK_ID = "4642074320795860992"
PROJECT_ID = "qwiklabs-gcp-02-87211ecaf6a5"
LOCATION = "us-east1"


def agentengine_memory_factory(uri: str, **kwargs):
    # Always target us-east1 where Reasoning Engine 4642074320795860992 is located
    engine_id = MEMORY_BANK_ID
    if uri and "://" in uri:
        part = uri.split("://")[-1].strip("/")
        if part:
            if "reasoningEngines/" in part:
                engine_id = part.split("reasoningEngines/")[-1]
            else:
                engine_id = part.split("/")[-1]

    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=LOCATION,
        agent_engine_id=engine_id,
    )


get_service_registry().register_memory_service(
    "agentengine", agentengine_memory_factory
)

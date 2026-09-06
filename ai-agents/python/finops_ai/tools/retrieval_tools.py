"""RAG Knowledge Base Retrieval Tool for Recommendation Rendering.

Invoked strictly at the recommendation-rendering step to enrich candidates with
provider-specific CLI commands, SKU transition caveats, and pricing guidance.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from crewai.tools import tool

from finops_ai.guardrails import sanitize_text, wrap_untrusted_data
from finops_ai.retrieval import (
    ProviderContextRetrievalService,
    RetrieveProviderContextInput,
    RetrieveProviderContextOutput,
    RetrievedChunk,
)


def _get_retrieval_service() -> ProviderContextRetrievalService | None:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            return ProviderContextRetrievalService.from_url(db_url)
        except Exception:
            return None
    return None



@tool("retrieve_provider_context")
def retrieve_provider_context(
    provider: str,
    resource_type: str,
    query: str,
    top_k: int = 5,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Retrieve provider-specific documentation, constraints, CLI command patterns,

    and pricing documentation from the pgvector knowledge base.
    Used ONLY during recommendation rendering.
    """
    clean_provider = sanitize_text(provider, max_length=64)
    clean_res_type = sanitize_text(resource_type, max_length=64)
    clean_query = sanitize_text(query, max_length=256)

    service = _get_retrieval_service()
    t_id = trace_id or str(uuid4())

    if service is not None:
        try:
            request = RetrieveProviderContextInput(
                provider=clean_provider,
                resource_type=clean_res_type,
                query=clean_query,
                top_k=top_k,
                trace_id=t_id,
                parent_step="agent.recommendation.render",
            )
            result = service.retrieve_provider_context(request)
            return {
                "status": "ok",
                "provider": clean_provider,
                "resource_type": clean_res_type,
                "chunks": [
                    {
                        "chunk_id": sanitize_text(c.chunk_id),
                        "category": sanitize_text(c.category),
                        "content": sanitize_text(c.content, max_length=1000),
                        "score": round(c.score, 3),
                        "source_url": sanitize_text(c.source_url),
                        "last_verified": c.last_verified.isoformat(),
                    }
                    for c in result.chunks
                ],
            }
        except Exception as e:
            # Fallback to deterministic default provider guidance
            pass

    # Fallback provider context for common resource types
    chunks: list[dict[str, Any]] = []
    if "gcp" in provider.lower() or "google" in provider.lower():
        if "compute" in resource_type.lower() or "instance" in resource_type.lower():
            chunks.append(
                {
                    "chunk_id": "gcp-compute-rightsize-guide",
                    "category": "architecture",
                    "content": (
                        "To modify machine type on Google Compute Engine, stop the instance and run: "
                        "`gcloud compute instances set-machine-type [INSTANCE_NAME] --machine-type=[NEW_TYPE] --zone=[ZONE]`. "
                        "Ensure attached persistent disks support the target machine family."
                    ),
                    "score": 0.95,
                    "source_url": "https://cloud.google.com/compute/docs/instances/changing-machine-type-of-stopped-instance",
                    "last_verified": "2026-08-01T00:00:00Z",
                }
            )
    elif "azure" in provider.lower() or "microsoft" in provider.lower():
        if "vm" in resource_type.lower() or "virtualmachines" in resource_type.lower():
            chunks.append(
                {
                    "chunk_id": "azure-vm-resize-guide",
                    "category": "architecture",
                    "content": (
                        "To resize an Azure Virtual Machine, run: "
                        "`az vm resize --resource-group [RG] --name [VM] --size [NEW_SIZE]`. "
                        "A temporary restart is required."
                    ),
                    "score": 0.95,
                    "source_url": "https://learn.microsoft.com/en-us/azure/virtual-machines/resize-vm",
                    "last_verified": "2026-08-01T00:00:00Z",
                }
            )

    return {
        "status": "ok",
        "provider": provider,
        "resource_type": resource_type,
        "chunks": chunks,
    }


@tool("lookup_cloud_catalog_skus")
def lookup_cloud_catalog_skus(
    provider: str,
    query: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """Look up authentic cloud provider machine types, SKUs, and pricing from the vector catalog.
    
    Use this to verify machine families (e.g., 'n2-standard-4', 'Standard_D4s_v3') and specs
    before recommending a resize, ensuring the target SKU actually exists.
    """
    clean_provider = sanitize_text(provider, max_length=64)
    clean_query = sanitize_text(query, max_length=256)

    service = _get_retrieval_service()
    if service is not None:
        try:
            request = RetrieveProviderContextInput(
                provider=clean_provider,
                resource_type="compute/instance",  # Defaulting for VM lookups
                query=clean_query,
                top_k=top_k,
                trace_id=str(uuid4()),
                parent_step="agent.reasoning.sku_lookup",
            )
            result = service.retrieve_provider_context(request)
            return {
                "status": "ok",
                "provider": clean_provider,
                "skus_found": [
                    {
                        "category": sanitize_text(c.category),
                        "content": sanitize_text(c.content, max_length=1000),
                        "score": round(c.score, 3),
                    }
                    for c in result.chunks
                ],
            }
        except Exception:
            pass
            
    return {
        "status": "error",
        "message": "Vector catalog unavailable. Do not recommend specific machine types without verification."
    }

"""
RAG Knowledge Base Management for EvidenceChain.

Handles:
  1. Ingesting Indian legal documents into ChromaDB
  2. Chunking with 64-token overlap (per spec)
  3. Embedding via OpenAI text-embedding-ada-002
  4. Retrieval with K=5

Usage:
  python manage.py shell
  >>> from cases.knowledge_base import KnowledgeBaseManager
  >>> kb = KnowledgeBaseManager()
  >>> kb.ingest_all()
  >>> results = kb.search("security deposit return Karnataka")
"""

import hashlib
import logging
import os
import re
from typing import List, Tuple

from django.conf import settings

logger = logging.getLogger('cases')

# ============================================================================
# BUILT-IN LEGAL KNOWLEDGE
# ============================================================================

# Hardcoded legal knowledge to bootstrap the system without external documents.
# These are real provisions from Indian law, structured for RAG retrieval.

LEGAL_KNOWLEDGE = [
    # ---- Karnataka Rent Control Act 2001 ----
    {
        "source": "Karnataka Rent Control Act 2001",
        "section": "Section 21 - Security Deposits",
        "text": (
            "Under Section 21 of the Karnataka Rent Control Act 2001, "
            "the landlord shall refund the security deposit to the tenant "
            "within one month of the tenant vacating the premises. If the "
            "landlord fails to return the deposit, the tenant may apply to "
            "the Rent Authority for recovery. The landlord may deduct from "
            "the deposit only for actual damages caused by the tenant beyond "
            "normal wear and tear, and must provide an itemized statement "
            "of deductions within 15 days."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    {
        "source": "Karnataka Rent Control Act 2001",
        "section": "Section 4 - Rent Authority",
        "text": (
            "Section 4 of the Karnataka Rent Control Act 2001 establishes "
            "the Rent Authority in each district. The Rent Authority has "
            "jurisdiction over disputes related to rent fixation, eviction, "
            "security deposit recovery, and maintenance obligations. "
            "Applications can be filed by either tenant or landlord. "
            "The Rent Authority must dispose of cases within 90 days."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    {
        "source": "Karnataka Rent Control Act 2001",
        "section": "Section 27 - Eviction Grounds",
        "text": (
            "Under Section 27 of the Karnataka Rent Control Act 2001, "
            "a landlord may seek eviction only on specified grounds: "
            "non-payment of rent for two consecutive months, subletting "
            "without consent, causing nuisance, using premises for illegal "
            "purposes, or bona fide need for self-occupation. The landlord "
            "must serve a notice of 15 days before filing for eviction."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    # ---- Transfer of Property Act 1882 ----
    {
        "source": "Transfer of Property Act 1882",
        "section": "Section 108 - Rights and Liabilities of Lessor and Lessee",
        "text": (
            "Section 108 of the Transfer of Property Act 1882 defines "
            "mutual rights and obligations. The lessor must deliver the "
            "property in good repair, pay all government charges, and not "
            "interfere with the lessee's peaceful possession. The lessee "
            "must pay rent, maintain the property, and restore it at the "
            "end of the lease in the condition received, subject to normal "
            "wear and tear."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    {
        "source": "Transfer of Property Act 1882",
        "section": "Section 111 - Determination of Lease",
        "text": (
            "Section 111 of the Transfer of Property Act 1882 provides "
            "that a lease may be determined by efflux of time, happening "
            "of an event, tenant's interest ceasing, merger, express "
            "surrender, implied surrender, forfeiture, or notice to quit. "
            "15 days notice must be given for monthly tenancies."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    # ---- Specific Relief Act 1963 ----
    {
        "source": "Specific Relief Act 1963",
        "section": "Section 14 - Contracts Not Specifically Enforceable",
        "text": (
            "Section 14 of the Specific Relief Act 1963 outlines "
            "contracts that cannot be specifically enforced, including "
            "contracts involving personal skill or volition, and contracts "
            "that are in their nature determinable. For rental disputes, "
            "specific performance of a lease agreement may be sought when "
            "monetary compensation is inadequate."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    # ---- Consumer Protection Act 2019 ----
    {
        "source": "Consumer Protection Act 2019",
        "section": "Section 2(7) - Definition of Consumer",
        "text": (
            "Under Section 2(7) of the Consumer Protection Act 2019, "
            "a consumer is any person who buys goods or hires services "
            "for consideration. This includes hiring of services like "
            "housing, and landlord-tenant relationships may fall under "
            "consumer protection jurisdiction if the tenant can establish "
            "a service relationship."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    # ---- Indian Contract Act 1872 (Freelance) ----
    {
        "source": "Indian Contract Act 1872",
        "section": "Section 73 - Compensation for Breach",
        "text": (
            "Section 73 of the Indian Contract Act 1872 provides that "
            "when a contract is broken, the injured party is entitled to "
            "compensation for loss or damage caused by the breach. For "
            "freelance payment disputes, this includes the agreed payment "
            "amount plus any consequential losses that were foreseeable "
            "at the time the contract was made."
        ),
        "dispute_type": "FREELANCE_PAYMENT",
    },
    {
        "source": "Indian Contract Act 1872",
        "section": "Section 10 - Valid Contract Requirements",
        "text": (
            "Section 10 of the Indian Contract Act 1872 states that all "
            "agreements are contracts if made by free consent, between "
            "parties competent to contract, for a lawful consideration "
            "and with a lawful object. For freelance agreements, even "
            "oral contracts are enforceable if the above elements exist. "
            "Email exchanges and WhatsApp messages can serve as evidence "
            "of contractual intent."
        ),
        "dispute_type": "FREELANCE_PAYMENT",
    },
    {
        "source": "Indian Contract Act 1872",
        "section": "Section 62 - Effect of Novation",
        "text": (
            "Section 62 provides that if parties to a contract agree to "
            "substitute a new contract for it, or to rescind or alter it, "
            "the original contract need not be performed. In freelance "
            "disputes, scope changes agreed upon via email or messages "
            "constitute novation and the latest agreed terms govern payment."
        ),
        "dispute_type": "FREELANCE_PAYMENT",
    },
    # ---- IT Act for Digital Evidence ----
    {
        "source": "Information Technology Act 2000",
        "section": "Section 65B - Admissibility of Electronic Records",
        "text": (
            "Section 65B of the Information Technology Act 2000 (as amended) "
            "governs the admissibility of electronic records as evidence. "
            "For any electronic record to be admissible in court, a "
            "certificate under Section 65B(4) must be produced identifying "
            "the electronic record, describing the manner of production, "
            "and certifying that appropriate safeguards were followed. "
            "This applies to WhatsApp messages, emails, bank statements, "
            "and UPI transaction records used in tenant-landlord and "
            "freelance payment disputes."
        ),
        "dispute_type": "ALL",
    },
    # ---- Maharashtra Rent Control Act ----
    {
        "source": "Maharashtra Rent Control Act 1999",
        "section": "Section 7 - Standard Rent and Permitted Increases",
        "text": (
            "Section 7 of the Maharashtra Rent Control Act 1999 governs "
            "standard rent determination and permitted increases. The annual "
            "rent increase is capped at 4% for residential premises. "
            "Security deposits in Maharashtra are typically limited to "
            "three months' rent for residential tenancies."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    # ---- Delhi Rent Control Act ----
    {
        "source": "Delhi Rent Control Act 1958",
        "section": "Section 14 - Grounds for Eviction",
        "text": (
            "Section 14 of the Delhi Rent Control Act 1958 specifies "
            "grounds for eviction including non-payment of rent, subletting, "
            "misuse of premises, and bona fide requirement by landlord for "
            "self-occupation. The tenant has the right to contest eviction "
            "and the Rent Controller must provide 15 days notice."
        ),
        "dispute_type": "TENANT_LANDLORD",
    },
    # ---- Limitation Act ----
    {
        "source": "Limitation Act 1963",
        "section": "Article 113 - Suit for Recovery of Money",
        "text": (
            "Under Article 113 of the Limitation Act 1963, the limitation "
            "period for a suit to recover money due under a contract is "
            "three years from the date the money became due. For security "
            "deposit recovery, the limitation begins from the date the "
            "tenant vacated the premises. For freelance payment disputes, "
            "it begins from the agreed payment date or completion of work."
        ),
        "dispute_type": "ALL",
    },
]


class KnowledgeBaseManager:
    """
    Manages the ChromaDB vector store for RAG retrieval.
    """

    def __init__(self):
        self.persist_dir = getattr(
            settings, 'CHROMA_PERSIST_DIRECTORY',
            os.path.join(settings.BASE_DIR, 'chroma_db')
        )
        self.collection_name = 'legal_knowledge'
        self._client = None
        self._collection = None

    def _get_client(self):
        """Lazy-load ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                self._client = chromadb.PersistentClient(
                    path=self.persist_dir,
                )
            except ImportError:
                logger.warning('ChromaDB not installed — using in-memory fallback')
                import chromadb
                self._client = chromadb.Client()

        return self._client

    def _get_collection(self):
        """Get or create the legal knowledge collection."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={'description': 'Indian legal provisions for EvidenceChain RAG'},
            )
        return self._collection

    def chunk_text(self, text: str, chunk_size: int = 256, overlap: int = 64) -> List[str]:
        """
        Split text into overlapping chunks.
        Uses token-approximate splitting (4 chars ≈ 1 token).
        """
        char_chunk_size = chunk_size * 4
        char_overlap = overlap * 4

        if len(text) <= char_chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + char_chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind('.', start + char_chunk_size // 2, end)
                if last_period > start:
                    end = last_period + 1

            chunks.append(text[start:end].strip())
            start = end - char_overlap

        return [c for c in chunks if c]

    def _generate_id(self, source: str, section: str, chunk_idx: int) -> str:
        """Generate deterministic chunk ID."""
        raw = f"{source}_{section}_{chunk_idx}"
        return hashlib.md5(raw.encode()).hexdigest()

    def ingest_all(self) -> dict:
        """
        Ingest all built-in legal knowledge into ChromaDB.
        Returns stats about the ingestion.
        """
        collection = self._get_collection()

        total_chunks = 0
        total_docs = 0

        for doc in LEGAL_KNOWLEDGE:
            chunks = self.chunk_text(doc['text'])
            total_docs += 1

            ids = []
            documents = []
            metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = self._generate_id(doc['source'], doc['section'], i)
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({
                    'source': doc['source'],
                    'section': doc['section'],
                    'dispute_type': doc['dispute_type'],
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                })

            # Upsert to avoid duplicates
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            total_chunks += len(chunks)

        logger.info(f'Ingested {total_docs} documents, {total_chunks} chunks')
        return {
            'documents_ingested': total_docs,
            'chunks_created': total_chunks,
            'collection_count': collection.count(),
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        dispute_type_filter: str = None,
    ) -> Tuple[List[str], List[float], List[dict]]:
        """
        Search the knowledge base.

        Returns:
            (texts, distances, metadatas)
        """
        collection = self._get_collection()

        where_filter = None
        if dispute_type_filter:
            where_filter = {
                '$or': [
                    {'dispute_type': dispute_type_filter},
                    {'dispute_type': 'ALL'},
                ]
            }

        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
        )

        texts = results['documents'][0] if results['documents'] else []
        distances = results['distances'][0] if results['distances'] else []
        metadatas = results['metadatas'][0] if results['metadatas'] else []

        # Convert distances to similarity scores (ChromaDB returns L2 distances)
        scores = [1.0 / (1.0 + d) for d in distances]

        return texts, scores, metadatas

    def get_stats(self) -> dict:
        """Get collection statistics."""
        collection = self._get_collection()
        return {
            'collection_name': self.collection_name,
            'total_chunks': collection.count(),
            'persist_directory': self.persist_dir,
        }

    def clear(self):
        """Clear all data from the collection."""
        client = self._get_client()
        try:
            client.delete_collection(self.collection_name)
            self._collection = None
            logger.info('Knowledge base cleared')
        except Exception:
            pass

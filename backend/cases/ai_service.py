# ai_service.py - AI Orchestration Layer
# Implements all GPT-4o prompts with RAG integration

import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import openai
from sentence_transformers import SentenceTransformer
import chromadb

from django.conf import settings
from .models import AILog, Case


class AIOrchestrationService:
    """
    Central service for all AI/LLM interactions
    Handles RAG retrieval, prompt construction, and response parsing
    """
    
    def __init__(self):
        # OpenAI Configuration
        openai.api_key = settings.OPENAI_API_KEY
        self.model_name = "gpt-4o"
        
        # Embedding Model (local)
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # ChromaDB Client
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIRECTORY
        )
        self.knowledge_base = self.chroma_client.get_collection(
            name="indian_legal_knowledge"
        )
    
    def _retrieve_context(self, query: str, top_k: int = 5, 
                         dispute_type_filter: Optional[str] = None) -> Tuple[List[str], List[float]]:
        """
        Retrieve top-k most similar chunks from knowledge base
        
        Returns:
            (chunks, similarity_scores)
        """
        start_time = time.time()
        
        # Embed query
        query_embedding = self.embedding_model.encode([query])[0]
        
        # Build metadata filter
        where_filter = {}
        if dispute_type_filter:
            where_filter = {
                "dispute_type_relevance": {"$contains": dispute_type_filter}
            }
        
        # Query ChromaDB
        results = self.knowledge_base.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where_filter if where_filter else None
        )
        
        chunks = results['documents'][0]
        distances = results['distances'][0]
        
        # Convert distances to similarity scores (cosine)
        # ChromaDB returns L2 distances, convert to cosine similarity
        similarity_scores = [1 - (d ** 2) / 2 for d in distances]
        
        latency_ms = int((time.time() - start_time) * 1000)
        print(f"RAG retrieval completed in {latency_ms}ms")
        
        return chunks, similarity_scores
    
    def _construct_rag_prompt(self, system_prompt: str, user_input: str, 
                             chunks: List[str], use_rag: bool = True) -> str:
        """
        Construct complete prompt with RAG context
        """
        if not use_rag or not chunks:
            return f"{system_prompt}\n\n[USER INPUT]\n{user_input}"
        
        # Format RAG chunks
        legal_context = "[LEGAL CONTEXT]\n"
        for i, chunk in enumerate(chunks, 1):
            legal_context += f"\nSource {i}:\n{chunk}\n"
        
        full_prompt = f"{system_prompt}\n\n{legal_context}\n\n[USER INPUT]\n{user_input}"
        return full_prompt
    
    def _call_gpt4o(self, prompt: str, temperature: float = 0.3, 
                    max_tokens: int = 1000, json_mode: bool = True) -> Dict:
        """
        Make API call to GPT-4o
        
        Returns:
            {
                'content': str,
                'tokens_used': int,
                'latency_ms': int
            }
        """
        start_time = time.time()
        
        messages = [
            {"role": "system", "content": "You are a precise legal information assistant."},
            {"role": "user", "content": prompt}
        ]
        
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        response = openai.ChatCompletion.create(**kwargs)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return {
            'content': response.choices[0].message.content,
            'tokens_used': response.usage.total_tokens,
            'latency_ms': latency_ms
        }
    
    def _log_ai_interaction(self, case_id: Optional[str], module: str, 
                           full_prompt: str, model_response: str,
                           retrieved_chunks: Optional[List[str]] = None,
                           chunk_scores: Optional[List[float]] = None,
                           tokens_used: int = 0, latency_ms: int = 0) -> str:
        """
        Log AI interaction to database
        Returns log_id
        """
        prompt_hash = hashlib.sha256(full_prompt.encode()).hexdigest()
        
        log = AILog.objects.create(
            case_id=case_id,
            module=module,
            prompt_hash=prompt_hash,
            full_prompt=full_prompt,
            model_response=model_response,
            retrieved_chunks=retrieved_chunks,
            chunk_similarity_scores=chunk_scores,
            model_name=self.model_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms
        )
        
        return str(log.log_id)
    
    # ========================================================================
    # MODULE 1: DISPUTE CLASSIFICATION
    # ========================================================================
    
    def extract_entities(self, case_id: str, narrative: str) -> Dict:
        """
        Step 1: Extract named entities from user narrative
        """
        system_prompt = """SYSTEM: You are a precise entity extractor for legal disputes in India.

TASK: Extract ONLY entities explicitly mentioned in the user's narrative.

OUTPUT FORMAT (JSON):
{
  "parties": ["Party Name 1", "Party Name 2"],
  "monetary_amounts": ["₹1,50,000", "₹80,000"],
  "dates": ["2024-01-15", "2024-03-20"],
  "locations": ["Bengaluru", "Karnataka", "India"],
  "legal_instruments": ["Rent Agreement", "Invoice", "Legal Notice"]
}

STRICT RULES:
1. Extract only explicitly present entities - DO NOT infer
2. Return null for absent fields (e.g., "dates": null if no dates mentioned)
3. Use ISO date format YYYY-MM-DD
4. Preserve exact monetary notation including ₹ symbol
5. Include both city and state for locations if mentioned"""
        
        full_prompt = self._construct_rag_prompt(
            system_prompt, 
            narrative, 
            chunks=[], 
            use_rag=False  # No RAG needed for entity extraction
        )
        
        response = self._call_gpt4o(full_prompt, temperature=0.1, max_tokens=500)
        
        # Log interaction
        log_id = self._log_ai_interaction(
            case_id=case_id,
            module='classification',
            full_prompt=full_prompt,
            model_response=response['content'],
            tokens_used=response['tokens_used'],
            latency_ms=response['latency_ms']
        )
        
        # Parse response
        try:
            entities = json.loads(response['content'])
        except json.JSONDecodeError:
            # Retry with corrective prompt if malformed
            corrective_prompt = f"{full_prompt}\n\nYour previous response was not valid JSON. Please return ONLY valid JSON with no additional text."
            response = self._call_gpt4o(corrective_prompt, temperature=0.1)
            entities = json.loads(response['content'])
        
        return {
            'entities': entities,
            'ai_log_id': log_id,
            'processing_time_ms': response['latency_ms']
        }
    
    def classify_dispute(self, case_id: str, entities: Dict, narrative: str) -> Dict:
        """
        Step 2: Classify dispute type
        """
        system_prompt = """SYSTEM: You are a legal dispute classifier for Indian legal contexts.

SUPPORTED CATEGORIES (select exactly ONE):
1. TENANT_LANDLORD: Rent disputes, security deposit recovery, eviction, property damage, lease violations
2. FREELANCE_PAYMENT: Unpaid freelance work, contract breaches, delayed payment, service disputes

OUTPUT FORMAT (JSON):
{
  "dispute_type": "TENANT_LANDLORD" | "FREELANCE_PAYMENT",
  "confidence": 0.0-1.0,
  "reasoning": "<one sentence explanation>"
}

CLASSIFICATION GUIDELINES:
- Confidence ≥ 0.7 required for automatic classification
- If confidence < 0.7, return both types as suggestions
- Base classification on factual indicators (parties, amounts, dates, context)

Factual Indicators:
TENANT_LANDLORD: Landlord-tenant relationship, rent/security deposit, property possession, eviction
FREELANCE_PAYMENT: Client-contractor relationship, service delivery, invoices, payment terms

RESPOND ONLY with valid JSON."""
        
        user_input = f"""Extracted Entities (JSON):
{json.dumps(entities, indent=2)}

Original Narrative:
{narrative}"""
        
        full_prompt = self._construct_rag_prompt(
            system_prompt,
            user_input,
            chunks=[],
            use_rag=False
        )
        
        response = self._call_gpt4o(full_prompt, temperature=0.2, max_tokens=300)
        
        log_id = self._log_ai_interaction(
            case_id=case_id,
            module='classification',
            full_prompt=full_prompt,
            model_response=response['content'],
            tokens_used=response['tokens_used'],
            latency_ms=response['latency_ms']
        )
        
        result = json.loads(response['content'])
        result['ai_log_id'] = log_id
        result['requires_manual_confirmation'] = result['confidence'] < 0.7
        
        return result
    
    # ========================================================================
    # MODULE 2: EVIDENCE PROCESSING
    # ========================================================================
    
    def classify_document(self, case_id: str, extracted_text: str) -> Dict:
        """
        Classify uploaded document type
        """
        system_prompt = """SYSTEM: You are a legal document classifier.

TASK: Classify this document into ONE category from the controlled vocabulary.

CONTROLLED VOCABULARY:
1. CONTRACT: Agreements, work orders, lease documents, service agreements, MOUs
2. RECEIPT: Payment receipts, deposit slips, transaction confirmations, bank statements
3. COMMUNICATION: Emails, WhatsApp chats, SMS, letters, Slack messages
4. PHOTOGRAPH: Images of property, products, conditions, damage, or evidence
5. LEGAL_NOTICE: Legal demands, lawyer letters, FIRs, court notices, summons
6. OTHER: Anything not fitting above categories

OUTPUT FORMAT (JSON):
{
  "classification": "CONTRACT" | "RECEIPT" | "COMMUNICATION" | "PHOTOGRAPH" | "LEGAL_NOTICE" | "OTHER",
  "confidence": 0.0-1.0,
  "reasoning": "<one sentence>"
}

CLASSIFICATION CRITERIA:
- CONTRACT: Legal language, terms & conditions, signatures, effective dates
- RECEIPT: Transaction IDs, amounts, dates, payment methods
- COMMUNICATION: Sender-receiver format, conversational tone, timestamps
- PHOTOGRAPH: Extracted text minimal or from image captions
- LEGAL_NOTICE: Legal jargon, statutory references, formal tone
- OTHER: Default if none of above clearly applies

RESPOND ONLY with valid JSON."""
        
        # Truncate text if too long
        text_preview = extracted_text[:2000] if len(extracted_text) > 2000 else extracted_text
        
        full_prompt = self._construct_rag_prompt(
            system_prompt,
            f"Document text:\n{text_preview}",
            chunks=[],
            use_rag=False
        )
        
        response = self._call_gpt4o(full_prompt, temperature=0.2, max_tokens=200)
        
        log_id = self._log_ai_interaction(
            case_id=case_id,
            module='document_processing',
            full_prompt=full_prompt,
            model_response=response['content'],
            tokens_used=response['tokens_used'],
            latency_ms=response['latency_ms']
        )
        
        result = json.loads(response['content'])
        result['ai_log_id'] = log_id
        
        return result
    
    def extract_document_entities(self, case_id: str, extracted_text: str) -> Dict:
        """
        Extract entities from document text
        Similar to narrative entity extraction but focused on documents
        """
        system_prompt = """Extract dates, parties, monetary amounts, and key clauses from this document.

Return JSON:
{
  "dates": ["YYYY-MM-DD"],
  "parties": ["Name 1", "Name 2"],
  "monetary_amounts": ["₹amount"],
  "key_clauses": ["Important clause text"]
}"""
        
        text_preview = extracted_text[:3000]
        
        full_prompt = self._construct_rag_prompt(
            system_prompt,
            text_preview,
            chunks=[],
            use_rag=False
        )
        
        response = self._call_gpt4o(full_prompt, temperature=0.1, max_tokens=500)
        
        log_id = self._log_ai_interaction(
            case_id=case_id,
            module='document_processing',
            full_prompt=full_prompt,
            model_response=response['content'],
            tokens_used=response['tokens_used'],
            latency_ms=response['latency_ms']
        )
        
        entities = json.loads(response['content'])
        return {'entities': entities, 'ai_log_id': log_id}
    
    # ========================================================================
    # MODULE 3: TIMELINE CONSTRUCTION
    # ========================================================================
    
    def deduplicate_events(self, case_id: str, event1: Dict, event2: Dict) -> Dict:
        """
        Determine if two events are duplicates
        """
        system_prompt = """SYSTEM: You are an event deduplication analyzer for legal timelines.

TASK: Determine if two events describe the same real-world occurrence.

OUTPUT FORMAT (JSON):
{
  "decision": "MERGE" | "KEEP_SEPARATE",
  "canonical_description": "<unified description if MERGE>",
  "reasoning": "<one sentence explanation>"
}

MERGE CRITERIA:
- Events describe the same action by same actors
- Dates within 3-day window (accounting for date discrepancies)
- Core facts align (amounts, parties, action type)

KEEP_SEPARATE CRITERIA:
- Different actions (e.g., "payment sent" vs "payment received")
- Same action type but different instances (e.g., two different rent payments)
- Dates >3 days apart with no explanation for discrepancy

RESPOND ONLY with valid JSON."""
        
        user_input = f"""EVENT 1:
Date: {event1.get('event_date', 'UNDATED')}
Description: {event1['action_description']}

EVENT 2:
Date: {event2.get('event_date', 'UNDATED')}
Description: {event2['action_description']}"""
        
        full_prompt = self._construct_rag_prompt(
            system_prompt,
            user_input,
            chunks=[],
            use_rag=False
        )
        
        response = self._call_gpt4o(full_prompt, temperature=0.2, max_tokens=300)
        
        log_id = self._log_ai_interaction(
            case_id=case_id,
            module='timeline',
            full_prompt=full_prompt,
            model_response=response['content'],
            tokens_used=response['tokens_used'],
            latency_ms=response['latency_ms']
        )
        
        result = json.loads(response['content'])
        result['ai_log_id'] = log_id
        
        return result
    
    def detect_timeline_gaps(self, case_id: str, chronological_events: List[Dict]) -> Dict:
        """
        Identify gaps in timeline
        """
        system_prompt = """SYSTEM: You are a factual event analyzer for legal timelines.

TASK: Identify ONLY temporal gaps where a logically expected event is absent based on the provided timeline.

STRICT RULES:
1. Identify only factual gaps (missing events that should logically exist)
2. DO NOT infer legal conclusions
3. DO NOT predict case outcomes
4. DO NOT suggest legal strategies
5. Base gaps only on logical sequence of events

OUTPUT FORMAT (JSON array):
[
  {
    "gap_after_event_id": "<uuid>",
    "description": "<factual description of missing event>",
    "suggested_question": "<neutral question to ask user about gap>"
  }
]

EXAMPLE GAPS:
✓ "No record of requesting deposit return before sending legal notice"
✓ "Missing move-out inspection date between lease end and deposit request"
✗ "Weak evidence of property damage" (legal conclusion)
✗ "Case likely to fail without witness statements" (outcome prediction)

RESPOND ONLY with valid JSON array. Return empty array [] if no gaps detected."""
        
        # Format timeline
        timeline_text = "TIMELINE:\n"
        for i, event in enumerate(chronological_events, 1):
            date_str = event.get('event_date', 'UNDATED')
            timeline_text += f"{i}. {date_str}: {event['action_description']}\n"
        
        full_prompt = self._construct_rag_prompt(
            system_prompt,
            timeline_text,
            chunks=[],
            use_rag=False
        )
        
        response = self._call_gpt4o(full_prompt, temperature=0.3, max_tokens=800)
        
        log_id = self._log_ai_interaction(
            case_id=case_id,
            module='timeline',
            full_prompt=full_prompt,
            model_response=response['content'],
            tokens_used=response['tokens_used'],
            latency_ms=response['latency_ms']
        )
        
        gaps = json.loads(response['content'])
        return {'gaps': gaps, 'ai_log_id': log_id}
    
    # ========================================================================
    # MODULE 4: CASE PACKET GENERATION
    # ========================================================================
    
    def generate_executive_summary(self, case_id: str, case_timeline: List[Dict], 
                                   evidence_list: List[Dict]) -> Dict:
        """
        Generate executive summary with RAG
        """
        case = Case.objects.get(case_id=case_id)
        
        # Retrieve relevant legal context
        query = f"{case.dispute_type} case summary {case.jurisdiction}"
        chunks, scores = self._retrieve_context(
            query, 
            top_k=5, 
            dispute_type_filter=case.dispute_type
        )
        
        system_prompt = """SYSTEM: You are writing a factual case summary for a legal preparation document.

HARD CONSTRAINTS:
1. Maximum 200 words
2. Summarize ONLY the factual situation
3. DO NOT characterize legal strength ("strong case", "weak position")
4. DO NOT predict outcomes ("likely to win", "may lose")
5. DO NOT recommend actions ("should file suit", "consider settlement")

WRITING GUIDELINES:
- Use past tense for completed events
- Present tense for current status
- Neutral, factual tone
- Chronological flow preferred
- Focus on: parties, dispute subject, key events, current stage

EXAMPLES OF ACCEPTABLE CONTENT:
✓ "The tenant paid a security deposit of ₹1,50,000 on January 5, 2024."
✓ "The landlord has not returned the deposit as of October 2024."
✓ "Communication records show three deposit return requests."

EXAMPLES OF PROHIBITED CONTENT:
✗ "The tenant has a strong case for deposit recovery."
✗ "This evidence may not be sufficient to win in court."
✗ "You should consider filing a consumer complaint."

RESPOND with plain text summary (no JSON, no markdown)."""
        
        # Format case details
        timeline_summary = "\n".join([
            f"- {e.get('event_date', 'UNDATED')}: {e['action_description']}"
            for e in case_timeline[:10]  # First 10 events
        ])
        
        evidence_summary = f"{len(evidence_list)} evidence items uploaded"
        
        user_input = f"""Timeline:
{timeline_summary}

Evidence:
{evidence_summary}"""
        
        full_prompt = self._construct_rag_prompt(
            system_prompt,
            user_input,
            chunks,
            use_rag=True
        )
        
        response = self._call_gpt4o(
            full_prompt, 
            temperature=0.4, 
            max_tokens=400,
            json_mode=False
        )
        
        log_id = self._log_ai_interaction(
            case_id=case_id,
            module='case_packet',
            full_prompt=full_prompt,
            model_response=response['content'],
            retrieved_chunks=chunks,
            chunk_scores=scores,
            tokens_used=response['tokens_used'],
            latency_ms=response['latency_ms']
        )
        
        return {
            'executive_summary': response['content'],
            'ai_log_id': log_id
        }
    
    def generate_lawyer_questions(self, case_id: str, gap_report: Dict, 
                                  timeline_gaps: List[Dict]) -> Dict:
        """
        Generate questions for user to ask lawyer
        """
        system_prompt = """SYSTEM: You generate factual questions for users to ask lawyers during consultation.

TASK: Based on evidence gaps and timeline gaps, generate 5-8 questions framed as information requests.

OUTPUT FORMAT (JSON array):
["Question 1", "Question 2", ...]

QUESTION GUIDELINES:
1. Frame as information requests, NOT legal assessments
2. Focus on missing factual details that a lawyer would need
3. DO NOT ask questions predicting outcomes
4. DO NOT suggest legal strategies
5. Use neutral language

EXAMPLES OF ACCEPTABLE QUESTIONS:
✓ "What additional documentation would strengthen the security deposit claim?"
✓ "Are there statutory deadlines for filing this type of dispute in Karnataka?"
✓ "What information from the landlord's side would be relevant?"

EXAMPLES OF PROHIBITED QUESTIONS:
✗ "Will I win this case?"
✗ "Should I file in civil court or consumer forum?"
✗ "How much compensation can I expect?"

RESPOND ONLY with valid JSON array of 5-8 questions."""
        
        user_input = f"""GAP REPORT:
{json.dumps(gap_report, indent=2)}

TIMELINE GAPS:
{json.dumps(timeline_gaps, indent=2)}"""
        
        full_prompt = self._construct_rag_prompt(
            system_prompt,
            user_input,
            chunks=[],
            use_rag=False
        )
        
        response = self._call_gpt4o(full_prompt, temperature=0.5, max_tokens=600)
        
        log_id = self._log_ai_interaction(
            case_id=case_id,
            module='case_packet',
            full_prompt=full_prompt,
            model_response=response['content'],
            tokens_used=response['tokens_used'],
            latency_ms=response['latency_ms']
        )
        
        questions = json.loads(response['content'])
        return {'lawyer_questions': questions, 'ai_log_id': log_id}


# Singleton instance
ai_service = AIOrchestrationService()

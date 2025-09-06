import time
from typing import List, Dict, Any, Optional
from langchain.schema import Document, HumanMessage, SystemMessage
from langchain_core.utils.utils import secret_from_env
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
import operator
from functools import lru_cache
import hashlib
from pydantic import BaseModel, Field

from app.services.llm_service import get_llm_from_bot_config
from app.services.adapter_service import create_domain_retrievers
from app.services.document_service import DocumentService


MEDICAL_RAG_PROMPT = """
You are a compassionate medical assistant specializing in autoimmune diseases. 
Your role is to support both healthcare professionals (for clinical knowledge) 
and patients (for understanding and reassurance). Always adapt your tone to the 
audience:

- If the user is a healthcare professional: 
  Provide concise, factual, and professional explanations in Indonesian, based on the knowledge base.
- If the user is a patient: 
  Provide clear, empathetic, and reassuring explanations in Indonesian, avoiding overly technical terms, 
  and ensuring the patient feels supported and understood.

Here is the context to use to answer the question:
{context}

Guidelines:
1. Always prioritize accuracy: if the query can be factually answered using the knowledge base, respond truthfully. If you want answer's is a paragraph, respond concisely (3–4 sentences) and if you want to answer with lists, make sure the answer isn't very long (10+ list points).
2. If the knowledge base does not contain the answer, reply with your generated answer but always add in the end
   exactly: "Informasi yang diberikan bisa saja salah. Jika ingin info lebih lengkap dan personal, Anda bisa hubungi tim kami"
3. For patients, use a compassionate and empathetic tone, as if you are a doctor consoling them about their health.
4. Restrict all answers to autoimmune conditions, their management, and their impact on daily life. 
   Do not provide unrelated or non-medical information.
5. If there are multiple sources of knowledge, prioritize the most recent and reliable one.
6. Always respond in Indonesian, matching the user's language and level of understanding.
7. Do not include opening or closing phrases like "Semoga membantu" or "Terima kasih"—just the answer itself.

User question:
{question}

Answer:
"""

DOC_GRADER_PROMPT = """Here is the retrieved document: 

{document}

Here is the user question: 

{question}

Carefully and objectively assess whether the document contains at least some information that is relevant to the question.

Return JSON with a single key: binary_score, that is 'yes' or 'no' to indicate relevance."""

MULTIVECTOR_ROUTER_PROMPT = """
You are a medical assistant. Choose the most relevant database (retriever) based on the user's question. 
Available options are:
{options_text}

Question: {question}

Return ONLY the retriever name (exactly as listed).
"""

class Grader(BaseModel):
    binary_score: str = Field(..., description="Either 'yes' or 'no'")


class AdvancedRagService:
    def __init__(self, document_service: DocumentService):
        self.document_service = document_service
        
    async def process_query(self, bot, query: str, user_id: str = "advanced_rag") -> Dict[str, Any]:
        try:
            llm = get_llm_from_bot_config(bot)
            llm_json = llm.llm.with_structured_output(Grader)

            retrievers = create_domain_retrievers(bot.id, self.document_service)
            
            workflow = self._create_workflow(llm, llm_json, retrievers)
            
            initial_state = {
                "question": query,
                "generation": "",
                "documents": [],
                "max_retries": bot.max_retries,
                "loop_step": 0,
                "documents_relevant": False
            }

            result = await workflow.ainvoke(initial_state)

            return {
                "message": result.get("generation", "No response generated"),
                "sources": self._format_sources(result.get("documents", [])),
                "saved": True,
                "metadata": {
                    "loop_steps": result.get("loop_step", 0),
                    "documents_found": len(result.get("documents", [])),
                    "workflow_completed": True
                }
            }
            
        except Exception as e:
            return {
                "message": f"Maaf, terjadi kesalahan dalam memproses pertanyaan Anda: {str(e)}",
                "sources": [],
                "saved": False,
                "metadata": {"error": str(e), "workflow_completed": False}
            }
        
    def _create_workflow(self, llm, llm_json, retrievers):

        class GraphState(TypedDict):
            question: str
            generation: str
            documents: List[Document]
            max_retries: int
            loop_step: int
            documents_relevant: bool
        
        async def retrieve(state):
            print("---RETRIEVE---")
            question = state["question"]
            loop_step = state.get("loop_step", 0)
            
            domain = await self._route_question(llm, question, retrievers)
            print(f"Router chose: {domain}")
            
            retriever_info = next(
                (r for r in retrievers if r["name"].lower() == domain.lower()), 
                retrievers[0]
            )
            
            documents = await retriever_info["retriever"].invoke(question)
            
            return {
                "documents": documents,
                "loop_step": loop_step + 1
            }
        
        async def grade_documents(state):
            print("---CHECK DOCUMENT RELEVANCE---")
            question = state["question"]
            documents = state["documents"]
            
            filtered_docs = []
            documents_relevant = False
            
            for doc in documents:
                doc_grader_prompt = DOC_GRADER_PROMPT.format(
                    document=doc.page_content, question=question
                )
                
                try:
                    result = await llm_json.ainvoke([
                        SystemMessage(content="You are a grader assessing relevance of a retrieved document to a user question."),
                        HumanMessage(content=doc_grader_prompt)
                    ])
                    
                    if result.binary_score.lower() == "yes":
                        print("---GRADE: DOCUMENT RELEVANT---")
                        filtered_docs.append(doc)
                        documents_relevant = True
                    else:
                        print("---GRADE: DOCUMENT NOT RELEVANT---")
                        
                except Exception as e:
                    print(f"Grading error: {e}, keeping document")
                    filtered_docs.append(doc)
                    documents_relevant = True
            
            return {
                "documents": filtered_docs,
                "documents_relevant": documents_relevant
            }
        
        async def generate(state):
            print("---GENERATE---")
            question = state["question"]
            documents = state["documents"]
            relevant = state.get("documents_relevant", True)
            
            if not documents or not relevant:
                return {
                    "generation": "Maaf, saya tidak menemukan informasi relevan di database."
                }

            context = self._format_documents_for_context(documents)

            rag_prompt = MEDICAL_RAG_PROMPT.format(
                context=context,
                question=question
            )
            
            try:
                response = await llm.generate([{"role": "user", "content": rag_prompt}])
                return {"generation": response}
            except Exception as e:
                return {"generation": f"Error generating response: {str(e)}"}
        
        def grade_documents_router(state):
            relevant = state.get("documents_relevant", True)
            loop_step = state.get("loop_step", 0)
            max_retries = state.get("max_retries", 3)
            
            if relevant:
                return "relevant"
            elif loop_step < max_retries:
                return "retry"
            else:
                return "max_retries"
        
        builder = StateGraph(state_schema=GraphState)

        builder.add_node("retrieve", retrieve)
        builder.add_node("grade_documents", grade_documents)
        builder.add_node("generate", generate)
        
        builder.set_entry_point("retrieve")
        builder.add_edge("retrieve", "grade_documents")

        builder.add_conditional_edges(
            "grade_documents",
            grade_documents_router,
            {
                "relevant": "generate",
                "retry": "retrieve", 
                "max_retries": "generate"
            }
        )
        
        builder.add_edge("generate", END)
        
        return builder.compile()
    
    async def _route_question(self, llm, question: str, retrievers: List[Dict]) -> str:
        options_text = "\n".join([
            f"- {r['name']}: {r['description']}" for r in retrievers
        ])
        
        router_prompt = MULTIVECTOR_ROUTER_PROMPT.format(
            options_text=options_text, 
            question=question
        )
        
        try:
            response = await llm.generate([{"role": "user", "content": router_prompt}])
            chosen = response.strip()

            if any(r["name"].lower() == chosen.lower() for r in retrievers):
                return chosen
            else:
                return retrievers[0]["name"]
                
        except Exception as e:
            print(f"Routing error: {e}")
            return retrievers[0]["name"]
    
    def _format_documents_for_context(self, documents: List[Document]) -> str:
        if not documents:
            return "Tidak ada informasi yang ditemukan."
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            similarity = doc.metadata.get("similarity", 0)
            source = doc.metadata.get("source", "Unknown")
            
            context_parts.append(
                f"[Sumber {i}: {source}, Relevansi: {similarity:.2f}]\n{doc.page_content}"
            )
        
        return "\n\n".join(context_parts)
    
    def _format_sources(self, documents: List[Document]) -> List[Dict[str, Any]]:
        sources = []
        for i, doc in enumerate(documents, 1):
            sources.append({
                "index": i,
                "content": doc.page_content,
                "similarity": doc.metadata.get("similarity", 0),
                "source_name": doc.metadata.get("source", "Unknown"),
                "metadata": doc.metadata
            })
        return sources
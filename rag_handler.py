"""
RAG (Retrieval-Augmented Generation) handler for document processing.
Manages PDF loading, embedding, and question-answering.
"""
import os
import tempfile
from typing import Optional
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_qdrant import QdrantVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from qdrant_utils import create_collection_if_not_exists, qdrant
from config import app_config


class RAGHandler:
    """Handles RAG operations for document-based question answering."""
    
    def __init__(self, gemini_api_key: str, collection_name: str = None):
        """
        Initialize RAG handler.
        
        Args:
            gemini_api_key: API key for Google Gemini
            collection_name: Name for Qdrant collection
        """
        self.gemini_key = gemini_api_key
        self.collection_name = collection_name or app_config.collection_name
        self.chain = None
        self.current_document = None
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name=app_config.embedding_model
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=app_config.chunk_size,
            chunk_overlap=app_config.chunk_overlap
        )
    
    def process_pdf(self, uploaded_file) -> bool:
        """
        Process uploaded PDF file and create RAG chain.
        
        Args:
            uploaded_file: Streamlit uploaded file object
            
        Returns:
            True if processing successful, False otherwise
        """
        try:
            # Save temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            # Load and split document
            loader = PyPDFLoader(tmp_path)
            documents = loader.load()
            splits = self.text_splitter.split_documents(documents)
            
            # Setup vector store
            self._setup_vector_store(splits)
            
            # Create RAG chain
            self._create_chain()
            
            # Store document name
            self.current_document = uploaded_file.name
            
            # Cleanup
            os.remove(tmp_path)
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to process PDF: {str(e)}")
    
    def _setup_vector_store(self, documents):
        """Setup Qdrant vector store with documents."""
        # Clear existing collection
        try:
            qdrant.delete_collection(collection_name=self.collection_name)
        except:
            pass
        
        # Create new collection
        create_collection_if_not_exists(collection_name=self.collection_name)
        
        # Create and populate vector store
        vectorstore = QdrantVectorStore(
            client=qdrant,
            embedding=self.embeddings,
            collection_name=self.collection_name
        )
        vectorstore.add_documents(documents=documents)
        
        self.retriever = vectorstore.as_retriever()
    
    def _create_chain(self):
        """Create the RAG chain for question answering."""
        system_prompt = (
            "Kamu adalah asisten yang menjawab pertanyaan berdasarkan "
            "konteks dokumen film yang diberikan. "
            "Jika jawaban tidak ada di dokumen, bilang tidak tahu. "
            "Jawab dengan lengkap dan jelas."
            "\n\n"
            "{context}"
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        llm = ChatGoogleGenerativeAI(
            model=app_config.llm_model,
            google_api_key=self.gemini_key
        )
        
        question_answer_chain = create_stuff_documents_chain(llm, prompt)
        self.chain = create_retrieval_chain(self.retriever, question_answer_chain)
    
    def query(self, question: str) -> str:
        """
        Query the RAG system with a question.
        
        Args:
            question: Question to ask about the document
            
        Returns:
            Answer from the RAG system
        """
        if not self.chain:
            raise ValueError("RAG chain not initialized. Process a PDF first.")
        
        response = self.chain.invoke({"input": question})
        return response["answer"]
    
    def is_ready(self) -> bool:
        """Check if RAG system is ready to answer questions."""
        return self.chain is not None
    
    def get_document_name(self) -> Optional[str]:
        """Get the name of the currently loaded document."""
        return self.current_document
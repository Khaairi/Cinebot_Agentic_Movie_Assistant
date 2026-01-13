"""
CineBot agent logic and conversation management.
Handles LLM interactions and tool execution.
"""
from typing import List, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import app_config


class PersonaManager:
    """Manages different persona configurations for the bot."""
    
    PERSONAS = {
        "Si Cinephile Gaul": {
            "description": "Bahasa gaul, santai, banyak slang, dan antusias.",
            "style": "Gunakan bahasa Indonesia gaul, santai, banyak slang, dan antusias."
        },
        "Kritikus Film": {
            "description": "Bahasa baku, elegan, puitis, dan analitis.",
            "style": "Gunakan bahasa Indonesia baku, elegan, puitis, dan analitis layaknya kritikus film profesional."
        }
    }
    
    @classmethod
    def get_system_message(cls, persona_name: str) -> SystemMessage:
        """
        Get system message for specified persona.
        
        Args:
            persona_name: Name of the persona
            
        Returns:
            SystemMessage with persona instructions
        """
        base_instruction = """Kamu adalah asisten AI ahli film. Tugasmu adalah merekomendasikan film, diskusi plot, dan memberi fakta menarik. 

Aturan Utama:
1. Jika user bertanya tentang film spesifik (sinopsis, siapa aktornya, rating) atau meminta rekomendasi terkait film, WAJIB panggil tool 'get_movie_info'.
2. Jika percakapan, baik dari user atau jawaban dari AI terdapat judul film, WAJIB panggil tool 'get_movie_info'.
3. Jika user meminta REKOMENDASI (misal: 'film horor', 'film sci-fi'), kamu harus melakukan langkah ini:
    a. Pikirkan 1-3 judul film populer yang sesuai dengan permintaan user.
    b. Langsung panggil tool 'get_movie_info' untuk SETIAP judul film yang kamu pikirkan tersebut secara paralel.
4. Jika tool berhasil mengambil data, jadikan data tersebut sebagai referensi untuk jawaban dan tambahkan detail dan fakta-fakta menarik seputar film tersebut.
5. Jika user mengirim gambar, analisalah gambar tersebut.
6. Jika user meminta untuk menambahkan film ke watchlist maka panggil tool 'add_to_watchlist'
7. Jika user meminta untuk menghapus atau membuang film dari watchlist maka panggil tool 'remove_from_watchlist'

PENTING:
- Jika menggunakan 'search_cinema_schedule', rangkum hasil pencarian Google menjadi daftar yang rapi (Bullet points).
- Jangan berhalusinasi jam tayang jika tidak ada di hasil pencarian.
"""
        
        persona = cls.PERSONAS.get(persona_name, cls.PERSONAS["Si Cinephile Gaul"])
        instruction = base_instruction + "\n" + persona["style"]
        
        return SystemMessage(content=instruction)
    
    @classmethod
    def get_persona_names(cls) -> List[str]:
        """Get list of available persona names."""
        return list(cls.PERSONAS.keys())


class ConversationManager:
    """Manages conversation history and message processing."""
    
    def __init__(self, persona: str = "Si Cinephile Gaul"):
        """
        Initialize conversation manager.
        
        Args:
            persona: Name of the persona to use
        """
        self.messages: List[Any] = [
            PersonaManager.get_system_message(persona)
        ]
    
    def add_message(self, message: Any):
        """Add a message to history."""
        self.messages.append(message)
    
    def get_messages(self) -> List[Any]:
        """Get all messages."""
        return self.messages
    
    def clear(self):
        """Clear conversation history (keeping system message)."""
        system_msg = self.messages[0]
        self.messages = [system_msg]
    
    def update_persona(self, persona: str):
        """Update persona and reset conversation."""
        self.messages = [PersonaManager.get_system_message(persona)]


class CineBotAgent:
    """Main agent that coordinates LLM and tools."""
    
    def __init__(
        self,
        api_key: str,
        tools: List[Any],
        conversation_manager: ConversationManager
    ):
        """
        Initialize CineBot agent.
        
        Args:
            api_key: Google Gemini API key
            tools: List of LangChain tools
            conversation_manager: Conversation manager instance
        """
        self.llm = ChatGoogleGenerativeAI(
            model=app_config.llm_model,
            google_api_key=api_key
        )
        self.llm = self.llm.bind_tools(tools)
        self.tools_dict = {tool.name: tool for tool in tools}
        self.conversation = conversation_manager
    
    def process_message(self, message: HumanMessage) -> AIMessage:
        """
        Process user message and return AI response.
        
        Args:
            message: User message
            
        Returns:
            AI response message
        """
        self.conversation.add_message(message)
        response = self.llm.invoke(self.conversation.get_messages())
        self.conversation.add_message(response)
        return response
    
    def execute_tools(self, response: AIMessage) -> AIMessage:
        """
        Execute any tool calls in the response.
        
        Args:
            response: AI response potentially containing tool calls
            
        Returns:
            Final AI response after tool execution
        """
        if not response.tool_calls:
            return response
        
        # Execute all tool calls
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            tool = self.tools_dict.get(tool_name)
            if tool:
                result = tool.invoke(tool_args)
                
                # Add tool result to conversation
                self.conversation.add_message(ToolMessage(
                    content=result,
                    tool_call_id=tool_call["id"],
                    name=tool_name
                ))
        
        # Get final response after tool execution
        final_response = self.llm.invoke(self.conversation.get_messages())
        self.conversation.add_message(final_response)
        
        return final_response
    
    def handle_message(self, message: HumanMessage) -> tuple[AIMessage, List[Dict]]:
        """
        Handle a complete message cycle including tool execution.
        
        Args:
            message: User message
            
        Returns:
            Tuple of (final_response, tool_results)
        """
        tool_results = []
        
        # Get initial response
        response = self.process_message(message)
        
        # Execute tools if any
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                tool = self.tools_dict.get(tool_name)
                if tool:
                    result = tool.invoke(tool_args)
                    tool_results.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result": result
                    })
                    
                    self.conversation.add_message(ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                        name=tool_name
                    ))
            
            # Get final response
            response = self.llm.invoke(self.conversation.get_messages())
            self.conversation.add_message(response)
        
        return response, tool_results
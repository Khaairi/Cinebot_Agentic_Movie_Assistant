"""
CineBot - AI Movie Assistant
Main Streamlit application entry point.
"""
import streamlit as st
import json
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

# Local imports
from config import api_config, app_config
from services import TMDBService, CinemaSearchService
from models import Watchlist
from rag_handler import RAGHandler
from tools import get_all_tools, set_tool_dependencies, ToolDependencies
from ui_components import UIComponents, MessageRenderer
from agent import CineBotAgent, ConversationManager, PersonaManager


class CineBotApp:
    """Main application class for CineBot."""
    
    def __init__(self):
        """Initialize the application."""
        self.ui = UIComponents()
        self.message_renderer = MessageRenderer(self.ui)
        self.setup_page_config()
        self.initialize_session_state()
    
    def setup_page_config(self):
        """Configure Streamlit page settings."""
        st.set_page_config(
            page_title=app_config.page_title,
            page_icon=app_config.page_icon,
            layout=app_config.layout
        )
    
    def initialize_session_state(self):
        """Initialize session state variables."""
        if "watchlist_obj" not in st.session_state:
            st.session_state["watchlist_obj"] = Watchlist()
        
        if "watchlist" not in st.session_state:
            st.session_state["watchlist"] = st.session_state["watchlist_obj"].to_list()
        
        if "rag_handler" not in st.session_state:
            st.session_state["rag_handler"] = None
        
        if "last_uploaded" not in st.session_state:
            st.session_state["last_uploaded"] = None
    
    def render_sidebar(self, gemini_key: str) -> tuple[str, str]:
        """
        Render sidebar with configuration options.
        
        Args:
            gemini_key: Gemini API key
            
        Returns:
            Tuple of (persona, gemini_key)
        """
        with st.sidebar:
            st.header("⚙️ Konfigurasi Bot")
            
            # Persona selection
            persona = st.radio(
                "Pilih Gaya Bicara:",
                PersonaManager.get_persona_names(),
                index=0
            )
            
            st.divider()
            
            # API Key input
            if not gemini_key:
                gemini_key = st.text_input(
                    "Masukkan Google Gemini API Key:",
                    type="password"
                )
                st.markdown(
                    "[Belum punya API Key? dapatkan di sini]"
                    "(https://aistudio.google.com/app/apikey)"
                )
            
                st.divider()
            
            # PDF upload section
            self.render_pdf_upload_section(gemini_key)
            
            st.divider()
            
            # Watchlist section
            self.render_watchlist_section()
            
            st.divider()
            
            # Reset button
            if st.button("🔄 Hapus Percakapan"):
                if "conversation_manager" in st.session_state:
                    st.session_state["conversation_manager"].clear()
                st.rerun()
        
        return persona, gemini_key
    
    def render_pdf_upload_section(self, gemini_key: str):
        """Render PDF upload and processing section."""
        st.header("📚 Chat Script/Buku")
        st.caption("Upload PDF script film atau buku, lalu tanya isinya di chat.")
        
        uploaded_pdf = st.file_uploader("Upload PDF", type="pdf")
        
        if uploaded_pdf and gemini_key:
            if (st.session_state["last_uploaded"] != uploaded_pdf.name):
                with st.spinner("Membaca & Mempelajari dokumen..."):
                    try:
                        if not st.session_state["rag_handler"]:
                            st.session_state["rag_handler"] = RAGHandler(gemini_key)
                        
                        st.session_state["rag_handler"].process_pdf(uploaded_pdf)
                        st.session_state["last_uploaded"] = uploaded_pdf.name
                        st.success("✅ Dokumen siap didiskusikan!")
                        
                    except Exception as e:
                        st.error(f"Gagal memproses dokumen: {e}")
    
    def render_watchlist_section(self):
        """Render watchlist management section."""
        st.header("📋 My Watchlist")
        
        # JSON upload
        uploaded_json = st.file_uploader(
            "Upload JSON",
            type=["json"],
            key="watchlist_uploader"
        )
        
        if uploaded_json:
            try:
                data = json.load(uploaded_json)
                st.session_state["watchlist_obj"].load_from_list(data)
                st.session_state["watchlist"] = data
                st.success("✅ Watchlist berhasil dimuat!")
            except Exception as e:
                st.error(f"Gagal memuat watchlist: {e}")
        
        # Display watchlist
        watchlist_data = st.session_state["watchlist_obj"].to_list()
        self.ui.render_watchlist(watchlist_data, key_suffix="sidebar")
    
    def initialize_agent(self, gemini_key: str, persona: str) -> CineBotAgent:
        """
        Initialize or get existing agent.
        
        Args:
            gemini_key: Gemini API key
            persona: Selected persona
            
        Returns:
            CineBotAgent instance
        """
        # Initialize services
        tmdb_service = TMDBService(api_config.tmdb_api_key)
        cinema_service = CinemaSearchService(
            api_config.google_api_key,
            api_config.google_cse_id
        )
        
        # Setup tool dependencies
        deps = ToolDependencies(
            tmdb_service=tmdb_service,
            cinema_service=cinema_service,
            watchlist=st.session_state["watchlist_obj"],
            rag_handler=st.session_state.get("rag_handler")
        )
        set_tool_dependencies(deps)
        
        # Initialize conversation manager
        if "conversation_manager" not in st.session_state:
            st.session_state["conversation_manager"] = ConversationManager(persona)
        
        # Initialize agent
        tools = get_all_tools()
        agent = CineBotAgent(
            api_key=gemini_key,
            tools=tools,
            conversation_manager=st.session_state["conversation_manager"]
        )
        
        return agent
    
    def render_chat_history(self):
        """Render conversation history."""
        messages = st.session_state["conversation_manager"].get_messages()
        
        for message in messages:
            # Skip system messages
            if isinstance(message, SystemMessage):
                continue
            
            # Tool messages shown as cards
            if isinstance(message, ToolMessage):
                self.message_renderer.render_tool_message(message)
                continue
            
            # Human messages
            if isinstance(message, HumanMessage):
                self.message_renderer.render_human_message(message)
            
            # AI messages
            elif isinstance(message, AIMessage):
                self.message_renderer.render_ai_message(message)
    
    def process_user_input(self, prompt, agent: CineBotAgent):
        """
        Process user input and generate response.
        
        Args:
            prompt: User input from chat
            agent: CineBotAgent instance
        """
        # Extract text and files
        user_text = prompt.text if hasattr(prompt, 'text') else prompt
        uploaded_files = getattr(prompt, 'files', [])
        
        # Build message content
        content_parts = []
        
        if user_text:
            content_parts.append({"type": "text", "text": user_text})
        elif uploaded_files:
            content_parts.append({
                "type": "text",
                "text": "Jelaskan gambar ini terkait dunia film."
            })
        
        # Add images
        if uploaded_files:
            for img_file in uploaded_files:
                image_url = self.ui.get_image_base64(img_file)
                if image_url:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    })
        
        # Display user message
        with st.chat_message("User"):
            if user_text:
                st.markdown(user_text)
            if uploaded_files:
                for img_file in uploaded_files:
                    st.image(img_file, width=150)
        
        # Create and process message
        human_message = HumanMessage(content=content_parts)
        
        with st.chat_message("AI"):
            with st.spinner("Sedang memproses..."):
                response, tool_results = agent.handle_message(human_message)
                
                # Display tool results
                for tool_result in tool_results:
                    self.display_tool_result(tool_result)
                
                # Display final response
                if response.content:
                    st.markdown(response.content)
        
        # Update watchlist in session state
        st.session_state["watchlist"] = st.session_state["watchlist_obj"].to_list()
    
    def display_tool_result(self, tool_result: dict):
        """
        Display tool execution results.
        
        Args:
            tool_result: Dictionary with tool execution info
        """
        tool_name = tool_result["name"]
        result_str = tool_result["result"]
        
        try:
            data = json.loads(result_str)
            
            if tool_name == "get_movie_info" and data.get("found"):
                self.ui.render_movie_card(data)
            
            elif tool_name == "recommend_from_watchlist":
                self.ui.render_recommendation_result(data)
            
            elif tool_name in ["add_to_watchlist", "remove_from_watchlist"]:
                self.ui.render_operation_status(data)
            
            elif tool_name == "search_cinema_schedule":
                st.markdown(result_str)
            
            elif tool_name == "ask_movie_script":
                st.info(f"📄 **Jawaban Dokumen:**\n\n{result_str}")
                
        except json.JSONDecodeError:
            st.markdown(result_str)
    
    def run(self):
        """Run the main application."""
        st.title("🎬 CINEBOT")
        st.caption("Diskusikan film favoritmu atau minta rekomendasi di sini!")
        
        # Get Gemini API key
        gemini_key = api_config.gemini_key
        
        # Render sidebar and get config
        persona, gemini_key = self.render_sidebar(gemini_key)
        
        # Check API key
        if not gemini_key:
            st.warning("⚠️ Masukkan Google Gemini API Key di sidebar untuk memulai.")
            st.stop()
        
        # Initialize agent
        agent = self.initialize_agent(gemini_key, persona)
        
        # Render chat history
        self.render_chat_history()
        
        # Chat input
        prompt = st.chat_input(
            "Tanya seputar film atau upload gambar",
            accept_file=True,
            file_type=["png", "jpg", "jpeg"]
        )
        
        if prompt:
            self.process_user_input(prompt, agent)
            st.rerun()


def main():
    """Application entry point."""
    app = CineBotApp()
    app.run()


if __name__ == "__main__":
    main()
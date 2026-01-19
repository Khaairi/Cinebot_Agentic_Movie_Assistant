"""
Streamlit UI components for CineBot.
Reusable UI elements and display functions.
"""
import streamlit as st
import pandas as pd
import json
import base64
from typing import Dict, List, Any


class UIComponents:
    """Collection of reusable UI components."""
    
    @staticmethod
    def render_movie_card(movie_data: Dict):
        """
        Render a movie information card.
        
        Args:
            movie_data: Dictionary containing movie information
        """
        with st.container(border=True):
            col1, col2 = st.columns([1, 2.5])
            
            with col1:
                st.image(movie_data['poster'], use_container_width=True)
            
            with col2:
                st.subheader(movie_data['title'])
                st.caption(
                    f"Original: {movie_data['original_title']} | "
                    f"Genre: {movie_data['genres']} | "
                    f"Rilis: {movie_data['release_date']} | "
                    f"Runtime: {movie_data['runtime']} Min"
                )
                st.write(f"⭐ **{movie_data['rating']}**")
                st.info(movie_data['overview'])
    
    @staticmethod
    def render_watchlist(watchlist_data: List[Dict], key_suffix: str = ""):
        """
        Render watchlist with DataFrame and controls.
        
        Args:
            watchlist_data: List of movies in watchlist
            key_suffix: Unique suffix for widget keys
        """
        if watchlist_data:
            df = pd.DataFrame(watchlist_data)
            st.dataframe(
                df[['title', 'genres', 'rating', 'runtime']],
                hide_index=True,
                use_container_width=True
            )
            
            json_str = json.dumps(watchlist_data, indent=4)
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "💾 Download",
                    json_str,
                    "watchlist.json",
                    "application/json",
                    key=f"dl_btn_{key_suffix}"
                )
            
            with col2:
                if st.button("🗑️ Clear All", key=f"clr_btn_{key_suffix}"):
                    st.session_state["watchlist"].clear()
                    st.rerun()
        else:
            st.info("📭 Watchlist kosong.")
    
    @staticmethod
    def render_recommendation_result(data: Dict):
        """
        Render movie recommendation results.
        
        Args:
            data: Recommendation result data
        """
        if data.get("found"):
            st.success(
                f"🎬 Terpilih {data['total_movies']} film "
                f"(Total: {data['total_runtime']} menit):"
            )
            
            for movie in data['movies']:
                with st.container(border=True):
                    st.write(f"**{movie['title']}**")
                    
                    genres = (
                        ", ".join(movie['genres'])
                        if isinstance(movie['genres'], list)
                        else movie['genres']
                    )
                    
                    st.caption(
                        f"⏱️ {movie['runtime']} min | "
                        f"⭐ {movie['rating']} | "
                        f"{genres}"
                    )
        else:
            st.warning(data.get("message"))
    
    @staticmethod
    def render_operation_status(data: Dict):
        """
        Render operation status message.
        
        Args:
            data: Status data with 'status' key
        """
        status = data.get("status")
        message = data.get("message", "")
        
        if status == "success":
            st.success(message)
            if "title" in data:
                st.toast(f"✅ {data['title']}")
        elif status == "exists":
            st.warning(message)
        else:
            st.error(message)
    
    @staticmethod
    def get_image_base64(uploaded_file) -> str:
        """
        Convert uploaded image to base64 data URL.
        
        Args:
            uploaded_file: Streamlit uploaded file
            
        Returns:
            Base64 encoded data URL
        """
        try:
            bytes_data = uploaded_file.getvalue()
            base64_str = base64.b64encode(bytes_data).decode('utf-8')
            return f"data:{uploaded_file.type};base64,{base64_str}"
        except Exception as e:
            st.error(f"Error processing image: {e}")
            return None


class MessageRenderer:
    """Handles rendering of chat messages."""
    
    def __init__(self, ui_components: UIComponents):
        """Initialize with UI components."""
        self.ui = ui_components

    def _get_clean_content(self, content: Any) -> str:
        """
        Helper to safely extract string text from mixed content types
        (String, List of Dicts, etc).
        """
        # If it's already a string, return it
        if isinstance(content, str):
            return content
        
        # If it's a list 
        if isinstance(content, list):
            text_parts = []
            for part in content:
                # Extract text from dict
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(str(part["text"]))
                # If the part itself is a string
                elif isinstance(part, str):
                    text_parts.append(part)
            return "".join(text_parts)
            
        # Fallback
        return str(content)
    
    def render_tool_message(self, message: Any):
        """
        Render tool execution results as visual cards.
        
        Args:
            message: ToolMessage object
        """
        with st.chat_message("AI"):
            try:
                content_str = self._get_clean_content(message.content)
                data = json.loads(content_str)
                
                # Movie info card
                if data.get("found") and "poster" in data:
                    self.ui.render_movie_card(data)
                
                # Recommendation results
                elif data.get("movies"):
                    self.ui.render_recommendation_result(data)
                
                # Operation status
                elif "status" in data:
                    self.ui.render_operation_status(data)
                    
            except (json.JSONDecodeError, KeyError):
                pass
    
    def render_human_message(self, message: Any):
        """
        Render user message with text and images.
        
        Args:
            message: HumanMessage object
        """
        with st.chat_message("User"):
            if isinstance(message.content, str):
                st.markdown(message.content)
            elif isinstance(message.content, list):
                for part in message.content:
                    if isinstance(part, dict):
                        if part.get('type') == 'text':
                            st.markdown(part['text'])
                        elif part.get('type') == 'image_url':
                            url = part.get('image_url', {}).get('url', '')
                            if url:
                                st.image(url, width=150)
    
    def render_ai_message(self, message: Any):
        """
        Render AI message.
        
        Args:
            message: AIMessage object
        """
        with st.chat_message("AI"):
            clean_text = self._get_clean_content(message.content)
            st.markdown(clean_text)
"""
LangChain tools for CineBot agent.
Defines all tool functions that the LLM can invoke.
"""
import json
from langchain_core.tools import tool
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services import TMDBService, CinemaSearchService
    from models import Watchlist
    from rag_handler import RAGHandler


class ToolDependencies:
    """Container for tool dependencies."""
    
    def __init__(
        self,
        tmdb_service: 'TMDBService',
        cinema_service: 'CinemaSearchService',
        watchlist: 'Watchlist',
        rag_handler: 'RAGHandler' = None
    ):
        self.tmdb = tmdb_service
        self.cinema = cinema_service
        self.watchlist = watchlist
        self.rag = rag_handler


# Global dependencies instance (will be set in main app)
_deps: ToolDependencies = None


def set_tool_dependencies(deps: ToolDependencies):
    """Set global tool dependencies."""
    global _deps
    _deps = deps


@tool
def get_movie_info(query: str) -> str:
    """
    Search for detailed movie information from TMDB database.
    
    Use this tool to get information about a specific movie including:
    - Title and original title
    - Synopsis/overview
    - Rating
    - Genres
    - Release date
    - Runtime
    - Poster image
    
    Args:
        query: Movie title to search for
        
    Returns:
        JSON string with movie details
    """
    try:
        result = _deps.tmdb.search_movie(query)
        
        if not result:
            return json.dumps({
                "found": False,
                "message": f"Film '{query}' tidak ditemukan di database."
            })
        
        return json.dumps(result)
        
    except Exception as e:
        return json.dumps({
            "found": False,
            "message": f"Error: {str(e)}"
        })


@tool
def search_cinema_schedule(location: str, movie_title: str = "") -> str:
    """
    Search for cinema schedules and ticket prices at a specific location.
    
    Use this tool when user asks about:
    - Cinema schedules
    - Ticket prices
    - Movies currently showing in a specific city
    
    Args:
        location: City or area to search
        movie_title: Optional specific movie title to search for
        
    Returns:
        Formatted search results with schedule information
    """
    return _deps.cinema.search_schedule(location, movie_title)


@tool
def add_to_watchlist(query: str) -> str:
    """
    Add a movie to the user's watchlist.
    
    Use this tool when user explicitly requests to add a movie to their watchlist.
    
    Args:
        query: Movie title to add
        
    Returns:
        JSON string with operation status
    """
    try:
        movie_data = _deps.tmdb.search_movie(query)
        
        if not movie_data or not movie_data.get("found"):
            return json.dumps({
                "status": "failed",
                "message": f"Film '{query}' tidak ditemukan."
            })
        
        watchlist_entry = {
            "id": movie_data["id"],
            "title": movie_data["title"],
            "genres": movie_data["genres"],
            "rating": movie_data["rating"],
            "runtime": movie_data["runtime"]
        }
        
        result = _deps.watchlist.add_movie(watchlist_entry)
        return json.dumps(result)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


@tool
def remove_from_watchlist(query: str) -> str:
    """
    Remove a movie from the user's watchlist.
    
    Use this tool when user explicitly requests to remove or delete a movie from their watchlist.
    
    Args:
        query: Movie title to remove
        
    Returns:
        JSON string with operation status
    """
    try:
        movie_data = _deps.tmdb.search_movie(query)
        
        if not movie_data or not movie_data.get("found"):
            return json.dumps({
                "status": "failed",
                "message": f"Film '{query}' tidak ditemukan di database."
            })
        
        result = _deps.watchlist.remove_movie(
            movie_data["id"],
            movie_data["title"]
        )
        return json.dumps(result)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


@tool
def recommend_from_watchlist(target_genre: str, max_minutes: int) -> str:
    """
    Create a viewing schedule from watchlist based on available time and genre preference.
    
    Use this tool when user wants movie recommendations from their watchlist
    considering their free time and preferred genre.
    
    Args:
        target_genre: Preferred genre (e.g., 'Horror', 'Action', 'Drama', or 'bebas' for any)
        max_minutes: Total available time in minutes
        
    Returns:
        JSON string with recommended movies
    """
    try:
        result = _deps.watchlist.recommend_by_time(target_genre, max_minutes)
        return json.dumps(result)
        
    except Exception as e:
        return json.dumps({
            "found": False,
            "message": f"Error: {str(e)}"
        })


@tool
def ask_movie_script(question: str) -> str:
    """
    Answer questions about uploaded movie scripts or PDF documents.
    
    Use this tool ONLY when user asks about the content of an uploaded PDF/script.
    Examples: "What happens on page 10?", "How does character A die?", "Summarize this script"
    
    Args:
        question: Question about the document content
        
    Returns:
        Answer based on document content
    """
    if not _deps.rag or not _deps.rag.is_ready():
        return "User belum mengunggah dokumen PDF. Minta user upload file dulu di sidebar."
    
    try:
        return _deps.rag.query(question)
    except Exception as e:
        return f"Error querying document: {str(e)}"


def get_all_tools():
    """Get list of all available tools."""
    return [
        get_movie_info,
        search_cinema_schedule,
        add_to_watchlist,
        remove_from_watchlist,
        recommend_from_watchlist,
        ask_movie_script
    ]
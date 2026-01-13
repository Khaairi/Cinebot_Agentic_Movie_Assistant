"""
External service integrations for CineBot.
Handles TMDB, Google Search, and other external APIs.
"""
import json
from typing import Dict, List, Optional
from tmdbv3api import TMDb, Movie
from langchain_community.utilities import GoogleSearchAPIWrapper


class TMDBService:
    """Service for interacting with The Movie Database API."""
    
    def __init__(self, api_key: str):
        """Initialize TMDB service with API key."""
        self.tmdb = TMDb()
        self.tmdb.language = 'en'
        self.tmdb.api_key = api_key
        self.movie_service = Movie()
    
    def search_movie(self, query: str) -> Optional[Dict]:
        """
        Search for a movie and return detailed information.
        
        Args:
            query: Movie title to search for
            
        Returns:
            Dictionary with movie details or None if not found
        """
        try:
            search_results = self.movie_service.search(query)
            
            if not search_results:
                return None
            
            movie = search_results[0]
            details = self.movie_service.details(movie.id)
            
            return self._format_movie_data(movie, details)
            
        except Exception as e:
            raise Exception(f"TMDB API error: {str(e)}")
    
    def _format_movie_data(self, movie, details) -> Dict:
        """Format movie data into a standardized dictionary."""
        genres = [genre["name"] for genre in details.genres]
        poster_url = (
            f"https://image.tmdb.org/t/p/w500{movie.poster_path}"
            if movie.poster_path
            else "https://via.placeholder.com/500x750?text=No+Poster"
        )
        
        return {
            "found": True,
            "id": movie.id,
            "title": movie.title,
            "original_title": movie.original_title,
            "overview": movie.overview,
            "rating": round(getattr(details, 'vote_average', 0), 1),
            "genres": ", ".join(genres),
            "release_date": movie.release_date,
            "poster": poster_url,
            "runtime": details.runtime
        }


class CinemaSearchService:
    """Service for searching cinema schedules using Google Search."""
    
    def __init__(self, api_key: str, cse_id: str):
        """Initialize cinema search service."""
        self.search = GoogleSearchAPIWrapper(
            google_api_key=api_key,
            google_cse_id=cse_id
        )
    
    def search_schedule(self, location: str, movie_title: str = "") -> str:
        """
        Search for cinema schedules at a specific location.
        
        Args:
            location: City or area to search
            movie_title: Optional specific movie title
            
        Returns:
            Formatted search results as string
        """
        try:
            query = self._build_search_query(location, movie_title)
            results = self.search.results(query, 1)
            
            if not results:
                return f"Maaf, tidak ditemukan jadwal di {location}."
            
            return self._format_search_results(results)
            
        except Exception as e:
            return f"Error searching cinema schedule: {str(e)}"
    
    def _build_search_query(self, location: str, movie_title: str) -> str:
        """Build optimized search query for cinema schedules."""
        base_query = "site:jadwalnonton.com/now-playing jadwal film"
        
        if movie_title:
            return f"{base_query} {movie_title} di bioskop {location} hari ini"
        return f"{base_query} bioskop di {location} hari ini"
    
    def _format_search_results(self, results: List[Dict]) -> str:
        """Format search results into readable text."""
        formatted = []
        for result in results:
            formatted.append(
                f"Source: {result['title']}\n"
                f"Snippet: {result['snippet']}"
            )
        return "\n\n".join(formatted)
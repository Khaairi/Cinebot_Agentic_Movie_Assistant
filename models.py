"""
Data models for CineBot application.
Defines structures for movies, watchlist, and other entities.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class Movie:
    """Movie data model."""
    id: int
    title: str
    genres: str
    rating: float
    runtime: int
    original_title: Optional[str] = None
    overview: Optional[str] = None
    release_date: Optional[str] = None
    poster: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert movie to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "genres": self.genres,
            "rating": f"{self.rating:.1f}",
            "runtime": self.runtime
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Create Movie instance from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            genres=data["genres"],
            rating=float(data.get("rating", 0)),
            runtime=data["runtime"],
            original_title=data.get("original_title"),
            overview=data.get("overview"),
            release_date=data.get("release_date"),
            poster=data.get("poster")
        )


class Watchlist:
    """Manages a collection of movies in a watchlist."""
    
    def __init__(self):
        """Initialize empty watchlist."""
        self.movies: List[Dict] = []
    
    def add_movie(self, movie_data: Dict) -> Dict:
        """
        Add a movie to the watchlist.
        
        Args:
            movie_data: Movie information dictionary
            
        Returns:
            Status dictionary with operation result
        """
        if self.contains(movie_data["id"]):
            return {
                "status": "exists",
                "title": movie_data["title"],
                "message": f"Film '{movie_data['title']}' sudah ada di watchlist."
            }
        
        self.movies.append(movie_data)
        return {
            "status": "success",
            "title": movie_data["title"],
            "message": f"Berhasil menambahkan '{movie_data['title']}' ke watchlist."
        }
    
    def remove_movie(self, movie_id: int, movie_title: str) -> Dict:
        """
        Remove a movie from the watchlist.
        
        Args:
            movie_id: ID of movie to remove
            movie_title: Title of movie (for messaging)
            
        Returns:
            Status dictionary with operation result
        """
        for i, movie in enumerate(self.movies):
            if movie['id'] == movie_id:
                self.movies.pop(i)
                return {
                    "status": "success",
                    "title": movie_title,
                    "message": f"Berhasil menghapus '{movie_title}' dari watchlist."
                }
        
        return {
            "status": "failed",
            "message": f"Film '{movie_title}' tidak ditemukan di watchlist."
        }
    
    def contains(self, movie_id: int) -> bool:
        """Check if a movie exists in the watchlist."""
        return any(movie['id'] == movie_id for movie in self.movies)
    
    def filter_by_genre(self, genre: str) -> List[Dict]:
        """Filter movies by genre."""
        if not genre or genre.lower() == "bebas":
            return self.movies
        
        genre_normalized = self._normalize_genre(genre)
        filtered = []
        
        for movie in self.movies:
            movie_genres = self._get_movie_genres(movie)
            if genre_normalized in movie_genres:
                filtered.append(movie)
        
        return filtered
    
    def recommend_by_time(self, genre: str, max_minutes: int) -> Dict:
        """
        Recommend movies based on available time and genre preference.
        
        Args:
            genre: Preferred genre
            max_minutes: Maximum available time in minutes
            
        Returns:
            Dictionary with recommended movies
        """
        if not self.movies:
            return {
                "found": False,
                "message": "Watchlist kosong. Tambahkan film dulu!"
            }
        
        filtered = self.filter_by_genre(genre)
        filtered.sort(key=lambda x: float(x.get('rating', 0)), reverse=True)
        
        selected = []
        total_time = 0
        
        for movie in filtered:
            runtime = int(movie.get('runtime', 0) or 0)
            if total_time + runtime <= max_minutes:
                selected.append(movie)
                total_time += runtime
        
        if not selected:
            return {
                "found": False,
                "message": f"Tidak ada film genre '{genre}' yang sesuai dengan waktu tersedia."
            }
        
        return {
            "found": True,
            "total_movies": len(selected),
            "total_runtime": total_time,
            "genre_requested": genre,
            "movies": selected
        }
    
    def _normalize_genre(self, genre: str) -> str:
        """Normalize genre name for comparison."""
        genre = genre.lower().strip()
        return 'science fiction' if genre == 'sci-fi' else genre
    
    def _get_movie_genres(self, movie: Dict) -> List[str]:
        """Extract and normalize genres from movie data."""
        raw_genres = movie.get('genres', [])
        if isinstance(raw_genres, str):
            return [g.strip().lower() for g in raw_genres.split(',')]
        return []
    
    def clear(self):
        """Clear all movies from watchlist."""
        self.movies.clear()
    
    def to_list(self) -> List[Dict]:
        """Get watchlist as list of dictionaries."""
        return self.movies
    
    def load_from_list(self, movies: List[Dict]):
        """Load watchlist from list of dictionaries."""
        self.movies = movies
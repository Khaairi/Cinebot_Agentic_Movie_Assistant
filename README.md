# Cinebot
**CineBot** is an intelligent, AI-powered conversational agent designed to be your ultimate movie companion. Built with **Streamlit** and powered by **Google Gemini 2.0 Flash**, this bot utilizes **Agentic Workflow (Function Calling)** to provide real-time movie data, recommendations, and personal watchlist management.

## Key Features

### Intelligent Chat & Personas
* Engage in natural conversations about movies, plots, and trivia.
* **Customizable Personas:** Choose between:
    * *Casual Cinephile:* Uses slang, friendly, and enthusiastic tone.
    * *Film Critic:* Formal, analytical, and poetic tone.

### Real-Time Movie Data (TMDB Integration)
* Fetches live data using **The Movie Database (TMDB) API**.
* Displays rich **Visual Cards** containing:
    * Posters.
    * Rating.
    * Release Date.
    * Runtime.
    * Synopsis/Overview.
 
### Now Playing in Theaters
* **Local Cinema Updates:** Fetches the list of movies currently showing specifically in **Indonesian cinemas** via Google Search API.

### Smart Watchlist Management
* **Add via Chat:** Simply tell the bot, *"Add Interstellar to my watchlist,"* and it handles the rest.
* **Sidebar UI:** View your current watchlist in a clean table format.
* **Import/Export:** Support for uploading and downloading your watchlist as a **JSON file**.

### Smart Schedule Curator
* **Personalized Marathon Planner:** The AI analyzes your watchlist to create a viewing schedule based on your available time.
* **Context Aware:** Just say, *"I have 6 hours free, recommend me horror movies from my list,"* and the bot will mathematically select movies that fit within that duration.

## Tech Stack
* **Frontend:** [Streamlit](https://streamlit.io/) (v1.41.0+)
* **Orchestration:** [LangChain](https://www.langchain.com/)
* **AI Model:** Google Gemini 2.0 Flash (via `langchain-google-genai`)
* **Data Source:** [TMDB API](https://www.themoviedb.org/) (via `tmdbv3api`)
* **Data Handling:** Pandas & JSON

## Installation & Setup

Follow these steps to run the project locally:

### 1. Clone the Repository
```bash
git clone https://github.com/Khaairi/Cinebot.git
cd Cinebot
```
### 2. Set Up Virtual Environment (Recommended)
```bash
python -m venv venv
venv\Scripts\activate
```
### 3. Install Dependencies
**Note:** This project requires Streamlit v1.41.0 or higher for the chat input features.
```bash
pip install -r requirements.txt
```
### 4. Run the Application
```bash
streamlit run app.py
```
## Project Structure
```bash
cinebot-project/
├── app.py              # Main application logic (Streamlit + LangChain)
├── requirements.txt    # Python dependencies
└── README.md           # Project documentation
```

## Documentation
| ![WhatsApp Image 2025-11-23 at 8 46 19 PM](https://github.com/user-attachments/assets/b7c44552-731e-43ce-93f9-0d78fd0d4ff9)     | ![WhatsApp Image 2025-11-23 at 8 46 36 PM](https://github.com/user-attachments/assets/67220ce7-bd9f-454b-a613-522dc435f0a9) |  
|--------------|---------------------------------------|
|    ![WhatsApp Image 2025-11-23 at 8 46 54 PM](https://github.com/user-attachments/assets/b5cf06c8-0cd5-4342-85fb-706cdf72d3e5)   | ![WhatsApp Image 2025-11-23 at 9 38 49 PM](https://github.com/user-attachments/assets/581ce0db-42d3-46be-8ce0-eac715f837e8)  |
|    ![WhatsApp Image 2025-12-22 at 10 24 35 AM](https://github.com/user-attachments/assets/83f290be-7e92-4973-84e6-9b4747ee425b)  | ![WhatsApp Image 2025-12-22 at 12 59 46 PM](https://github.com/user-attachments/assets/f94e533a-10e0-4812-9ad8-98d45ab07528) |












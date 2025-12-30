import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
import base64
from tmdbv3api import TMDb, Movie
import json
import pandas as pd
import os
from dotenv import load_dotenv
from langchain_community.utilities import GoogleSearchAPIWrapper
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_qdrant import QdrantVectorStore
import tempfile
from qdrant_utils import create_collection_if_not_exists
from qdrant_utils import qdrant
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

google_api_key = os.getenv("GOOGLE_API_KEY")
google_cse_id = os.getenv("GOOGLE_CSE_ID")
search = GoogleSearchAPIWrapper(google_api_key=google_api_key, google_cse_id=google_cse_id)
collection = "cinebot"

tmdb = TMDb()
tmdb.language = 'en'
tmdb.api_key = os.getenv("TMBD_API_KEY")
movie_service = Movie()

if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = []

def get_image_base64(uploaded_file):
    try:
        bytes_data = uploaded_file.getvalue()
        base64_str = base64.b64encode(bytes_data).decode('utf-8')
        # Format standar data URL untuk gambar
        return f"data:{uploaded_file.type};base64,{base64_str}"
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None
    
@tool
def search_cinema_schedule(location: str, movie_title: str = ""):
    """
    Gunakan alat ini jika user bertanya tentang JADWAL BIOSKOP, HARGA TIKET, 
    atau film yang tayang DI KOTA TERTENTU (misal: "Jadwal di Bandung", "XXI Jakarta").
    
    Alat ini melakukan pencarian Google untuk mendapatkan informasi terkini.
    """
    try:
        if movie_title:
            query = f"site:jadwalnonton.com/now-playing jadwal film {movie_title} di bioskop {location} hari ini"
        else:
            query = f"site:jadwalnonton.com/now-playing jadwal film bioskop di {location} hari ini"
        
        search_results = search.results(query, 1)
        
        if not search_results:
            return "Maaf, tidak ditemukan jadwal di Google untuk lokasi tersebut."
        
        parsed_results = []
        for res in search_results:
            parsed_results.append(f"Source: {res['title']}\nSnippet: {res['snippet']}")
            
        return "\n\n".join(parsed_results)
            
    except Exception as e:
        return f"Error Google Search: {str(e)}"
    
@tool
def get_movie_info(query: str):
    """
    Gunakan alat ini untuk mencari informasi detail film dari TMDB berdasarkan judul.
    Alat ini akan mengembalikan data JSON berisi detail dari film, seperti judul, sinopsis, rating, poster film, dan lainnya.
    """
    try:
        search = movie_service.search(query)
        
        if not search:
            return json.dumps({"found": False, "message": f"Film '{query}' tidak ditemukan di database."})

        # Ambil hasil paling atas (paling relevan)
        res = search[0]

        movie_id = res.id

        details = movie_service.details(movie_id)

        raw_rating = getattr(details, 'vote_average', 0)
        rating_fixed = round(raw_rating, 1)
        list_genres = []
        for item in details.genres:
            list_genres.append(item["name"])

        final_genres = ", ".join(list_genres)
        
        # Cek poster path
        if res.poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{res.poster_path}"
        else:
            poster_url = "https://via.placeholder.com/500x750?text=No+Poster"
        
        # Return data JSON lengkap
        return json.dumps({
            "found": True,
            "title": res.title,
            "original_title": res.original_title,
            "overview": res.overview,
            "rating": rating_fixed,
            "genres": final_genres,
            "release_date": res.release_date,
            "poster": poster_url,
            "runtime": details.runtime,
            "id": res.id
        })
    except Exception as e:
        return json.dumps({"found": False, "message": f"Error TMDB: {str(e)}"})
    
@tool
def add_to_watchlist(query: str):
    """
    Gunakan alat ini ketika user secara eksplisit meminta untuk menambahkan film ke dalam watchlist/daftar tontonan mereka.
    Input: Judul film.
    """
    try:
        # Cari dulu filmnya untuk memastikan data valid
        search = movie_service.search(query)
        if not search:
            return json.dumps({"status": "failed", "message": f"Film '{query}' tidak ditemukan, gagal menambahkan."})
        
        movie = search[0]

        movie_id = movie.id

        details = movie_service.details(movie_id)

        list_genres = []
        for item in details.genres:
            list_genres.append(item["name"])

        final_genres = ", ".join(list_genres)
        
        # Cek apakah sudah ada di watchlist
        current_ids = [m['id'] for m in st.session_state["watchlist"]]
        if movie.id in current_ids:
            return json.dumps({"status": "exists", "title": movie.title, "message": f"Film '{movie.title}' sudah ada di watchlist."})
        
        # Tambahkan ke Session State
        new_entry = {
            "id": movie.id,
            "title": movie.title,
            "genres": final_genres,
            "rating": f"{movie.vote_average:.1f}",
            "runtime": details.runtime
        }
        st.session_state["watchlist"].append(new_entry)
        
        return json.dumps({
            "status": "success", 
            "title": movie.title, 
            "message": f"Berhasil menambahkan '{movie.title}' ke watchlist."
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@tool
def remove_from_watchlist(query: str):
    """
    Gunakan alat ini ketika user secara eksplisit meminta untuk MENGHAPUS atau MEMBUANG film dari watchlist.
    Input: Judul film.
    """
    try:
        # 1. Cari dulu ID film berdasarkan judul agar akurat
        search = movie_service.search(query)
        if not search:
            return json.dumps({"status": "failed", "message": f"Film '{query}' tidak ditemukan di database, tidak bisa dihapus."})
        
        target_id = search[0].id
        target_title = search[0].title
        
        # 2. Cari di watchlist dan hapus
        found = False
        for i, movie in enumerate(st.session_state["watchlist"]):
            if movie['id'] == target_id:
                st.session_state["watchlist"].pop(i)
                found = True
                break
        
        if found:
            return json.dumps({
                "status": "success",
                "title": target_title,
                "message": f"Berhasil menghapus '{target_title}' dari watchlist."
            })
        else:
            return json.dumps({
                "status": "failed",
                "message": f"Film '{target_title}' tidak ditemukan di dalam watchlist kamu."
            })

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    
@tool
def recommend_from_watchlist(target_genre: str, max_minutes: int):
    """
    Gunakan alat ini jika user ingin dibuatkan jadwal/daftar tontonan dari watchlist mereka 
    berdasarkan waktu luang (durasi) dan genre yang diinginkan.
    
    Input:
        target_genre (str): Genre yang diinginkan user (misal: 'Horror', 'Action', 'Drama').
        max_minutes (int): Total waktu luang user dalam MENIT (misal: 6 jam = 360 menit).
    """
    watchlist = st.session_state["watchlist"]
    
    if not watchlist:
        return json.dumps({"found": False, "message": "Watchlist kamu kosong. Tambahkan film dulu!"})

    # 1. Filter berdasarkan Genre
    # Jika user bilang 'bebas', target_genre bisa diabaikan atau string kosong
    filtered_movies = []
    target_genre_lower = target_genre.lower().strip()
    if target_genre and target_genre.lower() != "bebas":
        for m in watchlist:
            raw_genres = m.get('genres', [])
            movie_genres_list = []
            if isinstance(raw_genres, str):
                movie_genres_list = [g.strip().lower() for g in raw_genres.split(',')]
            if target_genre_lower == 'sci-fi': target_genre_lower = 'science fiction'
            
            if target_genre_lower in movie_genres_list:
                filtered_movies.append(m)
    else:
        filtered_movies = watchlist # Ambil semua jika genre bebas

    # 2. Sorting: Prioritaskan Rating Tinggi
    filtered_movies.sort(key=lambda x: float(x.get('rating', 0)), reverse=True)

    # 3. Logika Seleksi (Greedy Algorithm sederhana)
    selected_movies = []
    current_time = 0
    
    for movie in filtered_movies:
        # Pastikan runtime dibaca sebagai integer
        try:
            runtime = int(movie.get('runtime', 0))
        except:
            runtime = 0
            
        if current_time + runtime <= max_minutes:
            selected_movies.append(movie)
            current_time += runtime

    if not selected_movies:
        return json.dumps({
            "found": False, 
            "message": f"Tidak ada film genre '{target_genre}' di watchlist yang cukup untuk waktumu."
        })

    return json.dumps({
        "found": True,
        "total_movies": len(selected_movies),
        "total_runtime": current_time,
        "genre_requested": target_genre,
        "movies": selected_movies
    })

@tool
def ask_movie_script(question: str):
    """
    Gunakan alat ini HANYA jika user bertanya tentang isi DOKUMEN/PDF/SCRIPT FILM yang mereka unggah.
    Contoh pertanyaan: "Apa yang terjadi di halaman 10?", "Bagaimana karakter A mati?", "Ringkaskan script ini".
    """
    if "rag_chain" not in st.session_state:
        return "User belum mengunggah dokumen PDF. Minta user upload file dulu di sidebar."
    
    try:
        # Jalankan RAG Chain yang sudah tersimpan di session state
        response = st.session_state["rag_chain"].invoke({"input": question})
        return response["answer"]
    except Exception as e:
        return f"Error RAG: {str(e)}"

st.set_page_config(
    page_title="CineBot",
    page_icon="🎬",
    layout="centered"
)

with st.sidebar:
    st.header("Konfigurasi Bot")

    # Memilih Persona
    persona = st.radio(
        "Pilih Gaya Bicara:",
        ["Si Cinephile Gaul", "Kritikus Film"],
        index=0
    )

    st.divider()
    
    # Input API Key atau masukkan di env
    if not os.getenv("GEMINI_KEY"):
        gemini_key = st.text_input("Masukkan Google Gemini API Key:", type="password")
        st.markdown("[Belum punya API Key? dapatkan di sini](https://aistudio.google.com/app/apikey)")
    else:
        gemini_key = os.getenv("GEMINI_KEY")

    
    st.header("Chat Script/Buku")
    st.caption("Upload PDF script film atau buku, lalu tanya isinya di chat.")
    uploaded_pdf = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_pdf and gemini_key:
        if "last_uploaded" not in st.session_state or st.session_state["last_uploaded"] != uploaded_pdf.name:
            with st.spinner("Membaca & Mempelajari dokumen..."):
                try:
                    # 1. Simpan file sementara
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(uploaded_pdf.getvalue())
                        tmp_file_path = tmp_file.name

                    # 2. Load PDF
                    loader = PyPDFLoader(tmp_file_path)
                    docs = loader.load()
                    print(docs)

                    # 3. Split Text
                    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                    splits = text_splitter.split_documents(docs)

                    # 4. Embeddings & Qdrant Vector Store
                    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

                    try:
                        qdrant.delete_collection(collection_name=collection)
                    except:
                        pass

                    create_collection_if_not_exists(collection_name=collection)

                    vectorstore = QdrantVectorStore(
                        client=qdrant,
                        embedding=embeddings,
                        collection_name=collection
                    )

                    vectorstore.add_documents(documents=splits)
                    
                    # 5. Create Chain
                    retriever = vectorstore.as_retriever()
                    
                    system_prompt = (
                        "Kamu adalah asisten yang menjawab pertanyaan berdasarkan konteks dokumen film yang diberikan. "
                        "Jika jawaban tidak ada di dokumen, bilang tidak tahu. "
                        "Jawab dengan lengkap dan jelas."
                        "\n\n"
                        "{context}"
                    )
                    prompt_rag = ChatPromptTemplate.from_messages([
                        ("system", system_prompt),
                        ("human", "{input}"),
                    ])
                    
                    question_answer_chain = create_stuff_documents_chain(
                        ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key), 
                        prompt_rag
                    )
                    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
                    
                    # Simpan ke Session State
                    st.session_state["rag_chain"] = rag_chain
                    st.session_state["last_uploaded"] = uploaded_pdf.name
                    st.success("✅ Dokumen siap didiskusikan!")
                    
                    # Hapus file temp
                    os.remove(tmp_file_path)
                    
                except Exception as e:
                    st.error(f"Gagal memproses dokumen: {e}")

    st.divider()

    st.header("My Watchlist")
    uploaded_watchlist = st.file_uploader("Upload JSON", type=["json"], key="static_uploader")
    if uploaded_watchlist:
        try:
            data = json.load(uploaded_watchlist)
            st.session_state["watchlist"] = data
        except: pass
    watchlist_placeholder = st.empty()
    
    st.divider()
    
    # Tombol Reset
    if st.button("Hapus Percakapan"):
        st.session_state.messages_history = []
        st.rerun()

def render_watchlist_ui(key_suffix="init"):
    with watchlist_placeholder.container():
        if st.session_state["watchlist"]:
            df = pd.DataFrame(st.session_state["watchlist"])
            st.dataframe(df[['title', 'genres', 'rating', 'runtime']], hide_index=True, use_container_width=True)
            
            json_str = json.dumps(st.session_state["watchlist"], indent=4)
            
            # Tombol Download & Clear harus punya key unik setiap kali render
            st.download_button(
                "Download", 
                json_str, 
                "watchlist.json", 
                "application/json", 
                key=f"dl_btn_{key_suffix}"
            )
            
            if st.button("Clear All", key=f"clr_btn_{key_suffix}"):
                st.session_state["watchlist"] = []
                st.rerun()
        else:
            st.info("Watchlist kosong.")
    
render_watchlist_ui("initial_load")

def get_system_message(persona_choice):
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

    if "Gaul" in persona_choice:
        instruction = base_instruction + " Gunakan bahasa Indonesia gaul, santai, banyak slang, dan antusias."
    else:
        instruction = base_instruction + " Gunakan bahasa Indonesia baku, elegan, puitis, dan analitis layaknya kritikus film profesional."
    
    return SystemMessage(content=instruction)

st.title("CINEBOT")
st.caption("Diskusikan film favoritmu atau minta rekomendasi di sini!")

if not gemini_key:
    st.warning("Masukkan Google Gemini API Key di sidebar untuk memulai.")
    st.stop()

tools = [get_movie_info, 
         add_to_watchlist, 
         remove_from_watchlist, 
         recommend_from_watchlist, 
         search_cinema_schedule,
         ask_movie_script]

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key)
llm = llm.bind_tools(tools)

if "messages_history" not in st.session_state:
    st.session_state["messages_history"] = [
        get_system_message(persona)
    ]
    
messages_history = st.session_state["messages_history"]

# Tampilkan messages history selama ini
for message in messages_history:
    # Tdk perlu tampilkan system message
    if type(message) is SystemMessage:
        continue
    
    if isinstance(message, ToolMessage):
        # render sebagai AI Message tapi dalam bentuk kartu visual
        with st.chat_message("AI"):
            try:
                # Parsing string JSON kembali jadi Dictionary
                data = json.loads(message.content)
                if data.get("found"):
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 2.5])
                        with col1:
                            st.image(data['poster'], use_container_width=True)
                        with col2:
                            st.subheader(data['title'])
                            st.caption(f"Original Title: {data['original_title']} | | Genre: {data['genres']} | Rilis: {data['release_date']} | Runtime: {data['runtime']} Min")
                            st.write(f"⭐ **{data['rating']}**")
                            st.info(data['overview'])
                elif data.get("movies"):
                    st.success(f"🎬 Terpilih {data['total_movies']} film (Total: {data['total_runtime']} menit):")
                    for mov in data['movies']:
                        with st.container(border=True):
                            st.write(f"**{mov['title']}**")
                            st.caption(f"⏱️ {mov['runtime']} min | ⭐ {mov['rating']}")
                elif "status" in data: 
                    if data["status"] == "success":
                        st.success(data["message"])
                    elif data["status"] == "exists":
                        st.warning(data["message"])
                    else:
                        st.error(data["message"])
            except:
                pass
        continue

    # Pilih role, apakah user/AI
    role = "User" if type(message) is HumanMessage else "AI"
    # Tampikan chatnya
    with st.chat_message(role):
        if isinstance(message.content, str):
             st.markdown(message.content)
        elif isinstance(message.content, list):
            # Jika list, berarti ada campuran teks dan gambar
            for part in message.content:
                if part.get('type') == 'text':
                    st.markdown(part['text'])
                elif part.get('type') == 'image_url':
                    # Tampilkan gambar dari data URL
                    st.image(part['image_url']['url'], width=150)

prompt = st.chat_input(
    "Tanya seputar film atau upload gambar",
    accept_file=True,
    file_type=["png", "jpg", "jpeg"]
)

if prompt:
    user_text = prompt.text
    uploaded_files = prompt.files
    content_parts = []

    if user_text:
        content_parts.append({"type": "text", "text": user_text})
    elif uploaded_files:
        # Jika user cuma upload gambar tanpa teks beri konteks default
        content_parts.append({"type": "text", "text": "Jelaskan gambar ini terkait dunia film."})

    if uploaded_files:
        for img_file in uploaded_files:
            image_data_url = get_image_base64(img_file)
            if image_data_url:
                # Format spesifik LangChain untuk Gemini Vision
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": image_data_url}
                })
    
    with st.chat_message("User"):
        if user_text:
            st.markdown(user_text)
        if uploaded_files:
            for img_file in uploaded_files:
                st.image(img_file, width=150)
    
    messages_history.append(HumanMessage(content_parts))

    with st.chat_message("AI"):
        with st.spinner("Sedang memproses..."):
            response = llm.invoke(messages_history)

            messages_history.append(response)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    # Eksekusi Tool TMDB
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    if tool_name == "get_movie_info":
                        raw_res = get_movie_info.invoke(tool_args)
                        data = json.loads(raw_res)
                        
                        # FITUR VISUAL CARD
                        if data.get("found"):
                            with st.container(border=True):
                                col1, col2 = st.columns([1, 2.5])
                                with col1:
                                    st.image(data['poster'], use_container_width=True)
                                with col2:
                                    st.subheader(data['title'])
                                    st.caption(f"Original Title: {data['original_title']} | | Genre: {data['genres']} | Rilis: {data['release_date']} | Runtime: {data['runtime']} Min")
                                    st.write(f"⭐ **{data['rating']}**")
                                    st.info(data['overview'])
                        else:
                            st.error(f"Film tidak ditemukan: {data.get('message')}")
                    elif tool_name == "add_to_watchlist":
                        raw_res = add_to_watchlist.invoke(tool_args)
                        data = json.loads(raw_res)
                        # Render Status Notification
                        if data["status"] == "success":
                            st.success(data["message"])
                            st.toast(f"✅ {data['title']} ditambahkan!")
                            render_watchlist_ui("refresh_add")
                        elif data["status"] == "exists":
                            st.warning(data["message"])
                        else:
                            st.error(data["message"])
                    elif tool_name == "remove_from_watchlist":
                        raw_res = remove_from_watchlist.invoke(tool_args)
                        data = json.loads(raw_res)
                        if data["status"] == "success":
                            st.success(data["message"])
                            st.toast(f"🗑️ {data['title']} dihapus!")
                            render_watchlist_ui("refresh_remove") # REFRESH UI
                        else:
                            st.error(data["message"])
                    elif tool_name == "recommend_from_watchlist":
                        raw_res = recommend_from_watchlist.invoke(tool_args)
                        data = json.loads(raw_res)
                        
                        if data.get("found"):
                            st.success(f"🎬 Ketemu nih! Ada {data['total_movies']} film Horror yang pas buat 6 jam:")
                            # Loop untuk menampilkan hasil pilihan
                            for mov in data['movies']:
                                with st.container(border=True):
                                    st.write(f"**{mov['title']}**")
                                    # Tampilkan list genre jika ada
                                    g_list = ", ".join(mov['genres']) if isinstance(mov['genres'], list) else mov['genres']
                                    st.caption(f"⏱️ {mov['runtime']} menit | ⭐ {mov['rating']} | {g_list}")
                        else:
                            st.warning(data.get("message"))
                    elif tool_name == "search_cinema_schedule":
                        raw_res = search_cinema_schedule.invoke(tool_args)
                        st.markdown(raw_res)
                    elif tool_name == "ask_movie_script":
                        raw_res = ask_movie_script.invoke(tool_args)
                        st.info(f"📄 **Jawaban Dokumen:**\n\n{raw_res}")
                    

                    # Simpan hasil tool ke history agar AI tahu datanya
                    messages_history.append(ToolMessage(
                        content=raw_res,
                        tool_call_id=tool_call["id"],
                        name=tool_name
                    ))

                final_res = llm.invoke(messages_history)
                st.markdown(final_res.content)
                messages_history.append(final_res)
            else:
                st.markdown(response.content)

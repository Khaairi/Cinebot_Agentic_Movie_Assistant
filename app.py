import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
import base64
from tmdbv3api import TMDb, Movie
import json
import pandas as pd

tmdb = TMDb()
tmdb.language = 'en'
tmdb.api_key = "a81911c9b55527fb6cb67697e66fb848"
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
        
        # Cek apakah sudah ada di watchlist
        current_ids = [m['id'] for m in st.session_state["watchlist"]]
        if movie.id in current_ids:
            return json.dumps({"status": "exists", "title": movie.title, "message": f"Film '{movie.title}' sudah ada di watchlist."})
        
        # Tambahkan ke Session State
        new_entry = {
            "id": movie.id,
            "title": movie.title,
            "release_date": movie.release_date,
            "rating": movie.vote_average
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
    
    # Input API Key
    gemini_key = st.text_input("Masukkan Google Gemini API Key:", type="password")
    st.markdown("[Belum punya API Key? dapatkan di sini](https://aistudio.google.com/app/apikey)")

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
            st.dataframe(df[['title', 'rating']], hide_index=True, use_container_width=True)
            
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

tools = [get_movie_info, add_to_watchlist, remove_from_watchlist]

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=gemini_key)
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
                            st.caption(f"Original Title: {data['original_title']} | Rilis: {data['release_date']} | Runtime: {data['runtime']} Min")
                            st.write(f"⭐ **{data['rating']}**")
                            st.info(data['overview'])
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
                                    st.caption(f"Original Title: {data['original_title']} | Rilis: {data['release_date']} | Runtime: {data['runtime']} Min")
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
import streamlit as st
import requests
import json
import time
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

API_BASE_URL = "http://localhost:8000"
API_KEY = "RAG_76f49853a8f141b1bb124229eb78c903"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

st.set_page_config(
    page_title="RAG Chatbot Admin",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        padding: 1rem 0;
        border-bottom: 2px solid #f0f2f6;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border-left: 4px solid #1f77b4;
    }
    .success-message {
        padding: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.25rem;
        color: #155724;
    }
    .error-message {
        padding: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.25rem;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)


def make_api_request(method, endpoint, data=None, params=None):
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers={k:v for k,v in HEADERS.items() if k != "Content-Type"}, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, headers=HEADERS, json=data, params=params)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=HEADERS, json=data, params=params)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers={k:v for k,v in HEADERS.items() if k != "Content-Type"}, params=params)
        
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"API Error {response.status_code}: {response.text}"
    
    except requests.exceptions.RequestException as e:
        return None, f"Connection Error: {str(e)}"

def safe_get(dictionary, key, default="N/A"):
    return dictionary.get(key, default)

def display_success(message):
    st.markdown(f'<div class="success-message">{message}</div>', unsafe_allow_html=True)

def display_error(message):
    st.markdown(f'<div class="error-message">{message}</div>', unsafe_allow_html=True)


st.sidebar.title("🤖 RAG Admin")
page = st.sidebar.selectbox(
    "Navigate to:",
    ["Dashboard", "Bot Management", "Document Management", "Chat Demo", "Integration Setup", "Analytics"]
)

if page == "Dashboard":
    st.markdown('<div class="main-header"><h1>📊 Dashboard Overview</h1></div>', unsafe_allow_html=True)
    
    health_data, health_error = make_api_request("GET", "/health")
    
    if health_error:
        st.error(f"API Connection Failed: {health_error}")
        st.stop()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if health_data and health_data.get("status") == "healthy":
            st.success("🟢 API Status: Healthy")
        else:
            st.error("🔴 API Status: Unhealthy")
    
    with col2:
        if health_data and health_data.get("database") == "connected":
            st.success("🟢 Database: Connected")
        else:
            st.error("🔴 Database: Disconnected")
    
    with col3:
        st.info(f"🔑 API Endpoint: {API_BASE_URL}")
    
    st.markdown("---")
    
    bots_data, bots_error = make_api_request("GET", "/api/v1/bots/")
    
    if bots_error:
        st.error(f"Failed to load bots: {bots_error}")
    else:
        total_bots = len(bots_data) if bots_data else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Bots", total_bots)
        
        with col2:
            total_docs = 0
            for bot in bots_data or []:
                bot_stats, _ = make_api_request("GET", f"/api/v1/bots/{bot['id']}/stats")
                if bot_stats:
                    total_docs += bot_stats.get("documents_count", 0)
            st.metric("Total of Document Chunks", total_docs)
        
        with col3:
            total_chats = 0
            for bot in bots_data or []:
                bot_stats, _ = make_api_request("GET", f"/api/v1/bots/{bot['id']}/stats")
                if bot_stats:
                    total_chats += bot_stats.get("chat_history_count", 0)
            st.metric("Total Chats", total_chats)
        
        with col4:
            total_integrations = 0
            for bot in bots_data or []:
                bot_stats, _ = make_api_request("GET", f"/api/v1/bots/{bot['id']}/stats")
                if bot_stats:
                    total_integrations += bot_stats.get("integrations_count", 0)
            st.metric("Total Integrations", total_integrations)
        

        if bots_data:
            st.subheader("📋 Recent Bots")
            df = pd.DataFrame(bots_data)
            df['createdAt'] = pd.to_datetime(df['createdAt']).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(df[['name', 'model', 'provider', 'createdAt']], use_container_width=True)

elif page == "Bot Management":
    st.markdown('<div class="main-header"><h1>🤖 Bot Management</h1></div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📋 List Bots", "➕ Create Bot", "⚙️ Bot Settings"])
    
    with tab1:
        bots_data, bots_error = make_api_request("GET", "/api/v1/bots/")
        
        if bots_error:
            st.error(f"Failed to load bots: {bots_error}")
        elif not bots_data:
            st.info("No bots found. Create your first bot!")
        else:
            for bot in bots_data:
                with st.expander(f"🤖 {bot['name']} ({safe_get(bot, 'model')})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**ID:** {bot['id']}")
                        st.write(f"**Description:** {safe_get(bot, 'description', 'No description')}")
                        st.write(f"**Provider:** {safe_get(bot, 'provider')}")
                        st.write(f"**Model:** {safe_get(bot, 'model')}")
                        st.write(f"**Temperature:** {safe_get(bot, 'temperature', 0.7)}")
                    
                    with col2:
                        st.write(f"**Top-K:** {safe_get(bot, 'top_k', 3)}")
                        st.write(f"**Similarity Threshold:** {safe_get(bot, 'similarity_threshold', 0.7)}")
                        st.write(f"**Created:** {pd.to_datetime(bot['createdAt']).strftime('%Y-%m-%d %H:%M')}")
                        

                        bot_stats, _ = make_api_request("GET", f"/api/v1/bots/{bot['id']}/stats")
                        if bot_stats:
                            st.write(f"**Documents:** {bot_stats.get('documents_count', 0)}")
                            st.write(f"**Chats:** {bot_stats.get('chat_history_count', 0)}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"🗑️ Delete", key=f"del_{bot['id']}"):
                            delete_result, delete_error = make_api_request("DELETE", f"/api/v1/bots/{bot['id']}")
                            if delete_error:
                                st.error(f"Delete failed: {delete_error}")
                            else:
                                st.success("Bot deleted successfully!")
                                st.rerun()
    
    with tab2:
        st.subheader("Create New Bot")
        
        with st.form("create_bot_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                bot_name = st.text_input("Bot Name*", placeholder="Medical Assistant")
                bot_description = st.text_area("Description", placeholder="RAG chatbot for medical queries")
                provider = st.selectbox("LLM Provider", ["mistral", "openai", "gemini"])
                model = st.text_input("Model", value="mistral-small-latest" if provider == "mistral" else "")
                use_advanced_rag = st.checkbox("Enable Advanced Medical RAG", False)
                max_retries = st.number_input("Max Retries (Advanced Medical RAG)", 1, 10, 3)
            
            with col2:
                temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
                max_tokens = st.number_input("Max Tokens", 100, 4000, 1000)
                top_k = st.number_input("Top-K (RAG)", 1, 20, 3)
                similarity_threshold = st.slider("Similarity Threshold", 0.0, 1.0, 0.7, 0.05)
            
            system_prompt = st.text_area(
                "System Prompt",
                value="You are a helpful AI assistant. Always respond in Indonesian and be compassionate.",
                height=100
            )
            
            rag_prompt = st.text_area(
                "RAG Prompt Template",
                value="Based on the following context, answer the question in Indonesian:\n\nContext: {context}\n\nQuestion: {question}\n\nAnswer:",
                height=100
            )
            
            col1, col2 = st.columns(2)
            with col1:
                use_reranking = st.checkbox("Use Reranking", True)
                use_multi_query = st.checkbox("Use Multi-Query", True)
            with col2:
                enable_chat_history = st.checkbox("Enable Chat History", True)
                enable_internet_search = st.checkbox("Enable Internet Search", False)
            
            submitted = st.form_submit_button("🚀 Create Bot")
            
            if submitted:
                if not bot_name:
                    st.error("Bot name is required!")
                else:
                    bot_data = {
                        "name": bot_name,
                        "description": bot_description,
                        "model": model,
                        "provider": provider,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_k": top_k,
                        "similarity_threshold": similarity_threshold,
                        "use_reranking": use_reranking,
                        "use_multi_query": use_multi_query,
                        "enable_chat_history": enable_chat_history,
                        "system_prompt": system_prompt,
                        "rag_prompt": rag_prompt,
                        "enable_internet_search": enable_internet_search,
                        "use_advanced_rag": use_advanced_rag,
                        "max_retries": max_retries
                    }
                    
                    result, error = make_api_request("POST", "/api/v1/bots/", bot_data)
                    
                    if error:
                        st.error(f"Failed to create bot: {error}")
                    else:
                        st.success(f"Bot '{bot_name}' created successfully!")
                        st.json(result)
    
    with tab3:
        bots_data, _ = make_api_request("GET", "/api/v1/bots/")
        
        if bots_data:
            selected_bot = st.selectbox("Select Bot to Update", 
                                      options=[bot['id'] for bot in bots_data],
                                      format_func=lambda x: next((bot['name'] for bot in bots_data if bot['id'] == x), x))
            
            if selected_bot:
                bot_details = next((bot for bot in bots_data if bot['id'] == selected_bot), None)
                
                if bot_details:
                    st.subheader(f"Update: {bot_details['name']}")
                    
                    with st.form("update_bot_form"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            new_name = st.text_input("Bot Name", value=bot_details['name'])
                            new_description = st.text_area("Description", value=safe_get(bot_details, 'description', ''))
                            new_temperature = st.slider("Temperature", 0.0, 2.0, float(safe_get(bot_details, 'temperature', 0.7)), 0.1)
                        
                        with col2:
                            new_top_k = st.number_input("Top-K", 1, 20, safe_get(bot_details, 'top_k', 3))
                            new_similarity = st.slider("Similarity Threshold", 0.0, 1.0, float(safe_get(bot_details, 'similarity_threshold', 0.7)), 0.05)
                        
                        new_system_prompt = st.text_area("System Prompt", value=safe_get(bot_details, 'system_prompt', ''), height=100)
                        
                        if st.form_submit_button("💾 Update Bot"):
                            update_data = {
                                "name": new_name,
                                "description": new_description,
                                "temperature": new_temperature,
                                "top_k": new_top_k,
                                "similarity_threshold": new_similarity,
                                "system_prompt": new_system_prompt
                            }
                            
                            result, error = make_api_request("PUT", f"/api/v1/bots/{selected_bot}", update_data)
                            
                            if error:
                                st.error(f"Update failed: {error}")
                            else:
                                st.success("Bot updated successfully!")
                                st.rerun()
        else:
            st.info("No bots available to update.")

elif page == "Document Management":
    st.markdown('<div class="main-header"><h1>📁 Document Management</h1></div>', unsafe_allow_html=True)
    
    bots_data, bots_error = make_api_request("GET", "/api/v1/bots/")
    
    if bots_error or not bots_data:
        st.error("No bots available. Create a bot first!")
        st.stop()
    
    selected_bot_id = st.selectbox("Select Bot", 
                                 options=[bot['id'] for bot in bots_data],
                                 format_func=lambda x: next((bot['name'] for bot in bots_data if bot['id'] == x), x))
    
    if selected_bot_id:
        bot_info = next((bot for bot in bots_data if bot['id'] == selected_bot_id), None)
        is_advanced_rag = bot_info and bot_info.get('use_advanced_rag', False)
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Sources", "📄 Upload Text", "📎 Upload File", "🌐 Upload URL"])
        
        with tab1:
            sources_data, sources_error = make_api_request("GET", "/api/v1/documents/sources", params={"bot_id": selected_bot_id})
            
            if sources_error:
                st.error(f"Failed to load sources: {sources_error}")
            elif not sources_data:
                st.info("No sources found. Upload some documents!")
            else:
                st.subheader("📋 Document Sources")
                
                for source in sources_data:
                    status_color = "🟢" if source['status'] == 'completed' else "🟡" if source['status'] == 'processing' else "🔴"
                    
                    with st.expander(f"{status_color} {source['name']} ({source['type']})"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**ID:** {source['id']}")
                            st.write(f"**Type:** {source['type']}")
                            st.write(f"**Status:** {source['status']}")
                            st.write(f"**Size:** {safe_get(source, 'file_size_mb', 0):.2f} MB")
                        
                        with col2:
                            st.write(f"**Created:** {pd.to_datetime(source['createdAt']).strftime('%Y-%m-%d %H:%M')}")
                            if source.get('error_message'):
                                st.error(f"Error: {source['error_message']}")
                        
                        if source['status'] == 'processing':
                            status_data, _ = make_api_request("GET", f"/api/v1/documents/sources/{source['id']}/status", 
                                                            params={"bot_id": selected_bot_id})
                            if status_data:
                                progress = status_data.get('progress', 0)
                                st.progress(progress)
                                st.write(f"Progress: {progress*100:.1f}%")
                        
                        if st.button(f"🗑️ Delete", key=f"del_source_{source['id']}"):
                            delete_result, delete_error = make_api_request("DELETE", f"/api/v1/documents/sources/{source['id']}", 
                                                                         params={"bot_id": selected_bot_id})
                            if delete_error:
                                st.error(f"Delete failed: {delete_error}")
                            else:
                                st.success("Source deleted successfully!")
                                st.rerun()
        
        with tab2:  # Upload Text
            st.subheader("📄 Upload Text Content")
            
            with st.form("upload_text_form"):
                text_name = st.text_input("Document Name*", placeholder="Medical Guidelines")
                text_content = st.text_area("Text Content*", height=200, 
                                        placeholder="Enter your document content here...")
                
                # Conditional domain selection
                medical_domain = None
                if is_advanced_rag:
                    medical_domain = st.selectbox(
                        "Medical Domain (Required for Advanced Medical RAG)",
                        options=["", "RA", "SLE", "Arthritis", "Spondyloarthritis", "Vasculitis"],
                        help="Select medical domain for better routing in Advanced Medical RAG"
                    )
                    if not medical_domain:
                        st.warning("⚠️ Medical domain is recommended for Advanced Medical RAG bots")
                else:
                    st.info("ℹ️ Medical domain selection available for Advanced Medical RAG bots only")
                
                submitted = st.form_submit_button("📤 Upload Text")
                
                if submitted:
                    if not text_name or not text_content:
                        st.error("Name and content are required!")
                    else:
                        upload_data = {
                            "name": text_name,
                            "content": text_content,
                            "medical_domain": medical_domain if medical_domain else None
                        }
                        
                        result, error = make_api_request("POST", "/api/v1/documents/upload-text", 
                                                    upload_data, params={"bot_id": selected_bot_id})
                        
                        if error:
                            st.error(f"Upload failed: {error}")
                        else:
                            st.success("Text uploaded successfully! Processing in background...")
                            st.json(result)

        with tab3:  # Upload File  
            st.subheader("📎 Upload File")
            
            uploaded_file = st.file_uploader("Choose file", type=['txt', 'pdf'], 
                                        help="Supported formats: .txt, .pdf (max 10MB)")
            
            # Conditional domain selection
            medical_domain_file = None
            if is_advanced_rag:
                medical_domain_file = st.selectbox(
                    "Medical Domain (Required for Advanced Medical RAG)",
                    options=["", "RA", "SLE", "Arthritis", "Spondyloarthritis", "Vasculitis"],
                    key="file_domain",
                    help="Select medical domain for better routing in Advanced Medical RAG"
                )
                if not medical_domain_file:
                    st.warning("⚠️ Medical domain is recommended for Advanced Medical RAG bots")
            else:
                st.info("ℹ️ Medical domain selection available for Advanced Medical RAG bots only")
            
            if uploaded_file and st.button("Upload File"):
                if uploaded_file.size > 10 * 1024 * 1024:
                    st.error("File too large! Maximum size is 10MB.")
                else:
                    try:
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {'medical_domain': medical_domain_file if medical_domain_file and medical_domain_file != '' else None}
                        headers_no_content_type = {k: v for k, v in HEADERS.items() if k != "Content-Type"}
                        
                        response = requests.post(
                            f"{API_BASE_URL}/api/v1/documents/upload-file",
                            headers=headers_no_content_type,
                            files=files,
                            data=data,
                            params={"bot_id": selected_bot_id}
                        )
                        
                        if response.status_code == 200:
                            st.success("File uploaded successfully! Processing in background...")
                            st.json(response.json())
                        else:
                            st.error(f"Upload failed: {response.text}")
                    
                    except Exception as e:
                        st.error(f"Upload error: {str(e)}")

        with tab4:  # Upload URL
            st.subheader("Upload from URL")
            
            with st.form("upload_url_form"):
                url_name = st.text_input("Source Name*", placeholder="Wikipedia Article")
                url_content = st.text_input("URL*", placeholder="https://example.com/article")
                
                medical_domain_url = st.selectbox(
                    "Medical Domain (Optional)",
                    options=["", "RA", "SLE", "Arthritis", "Spondyloarthritis", "Vasculitis"],
                    key="url_domain",
                    help="Select medical domain for better routing in Advanced Medical RAG"
                )
                
                submitted = st.form_submit_button("Upload URL")
                
                if submitted:
                    if not url_name or not url_content:
                        st.error("Name and URL are required!")
                    else:
                        upload_data = {
                            "name": url_name,
                            "url": url_content,
                            "medical_domain": medical_domain_url if medical_domain_url else None
                        }
                        
                        result, error = make_api_request("POST", "/api/v1/documents/upload-url", 
                                                    upload_data, params={"bot_id": selected_bot_id})
                        
                        if error:
                            st.error(f"Upload failed: {error}")
                        else:
                            st.success("URL uploaded successfully! Processing in background...")
                            st.json(result)
        
        st.markdown("---")
        doc_stats, doc_stats_error = make_api_request("GET", "/api/v1/documents/stats", params={"bot_id": selected_bot_id})
        
        if doc_stats_error:
            st.warning(f"Could not load document statistics: {doc_stats_error}")
        elif doc_stats:
            st.subheader("📊 Document Statistics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Sources", safe_get(doc_stats.get('sources', {}), 'total', 0))
            with col2:
                st.metric("Completed", safe_get(doc_stats.get('sources', {}), 'completed', 0))
            with col3:
                st.metric("Processing", safe_get(doc_stats.get('sources', {}), 'processing', 0))
            with col4:
                st.metric("Total Size", f"{safe_get(doc_stats.get('storage', {}), 'total_size_mb', 0):.2f} MB")

elif page == "Chat Demo":
    st.markdown('<div class="main-header"><h1>💬 Chat Demo</h1></div>', unsafe_allow_html=True)
    
    bots_data, bots_error = make_api_request("GET", "/api/v1/bots/")
    
    if bots_error or not bots_data:
        st.error("No bots available. Create a bot first!")
        st.stop()
    
    selected_bot_id = st.selectbox("Select Bot for Demo", 
                                 options=[bot['id'] for bot in bots_data],
                                 format_func=lambda x: next((bot['name'] for bot in bots_data if bot['id'] == x), x))
    
    if selected_bot_id:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "session_id" not in st.session_state:
            st.session_state.session_id = f"demo_{int(time.time())}"
        
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                if message["role"] == "assistant" and message.get("sources"):
                    with st.expander("📚 Sources Used"):
                        for i, source in enumerate(message["sources"], 1):
                            st.write(f"**{i}. {source['source_name']}** (similarity: {source['similarity']:.2f})")
                            st.write(f"_{source['content'][:200]}..._")
        
        if prompt := st.chat_input("Ask me about medical topics..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    chat_data = {
                        "message": prompt,
                        "user_id": "demo_user",
                        "session_id": st.session_state.session_id,
                        "platform": "web",
                        "use_history": True,
                        "save_to_db": True
                    }
                    result, error = make_api_request("POST", "/api/v1/chat/", chat_data, params={"bot_id": selected_bot_id})
                
                if error:
                    st.error(f"Chat failed: {error}")
                    response_text = "Sorry, I encountered an error processing your message."
                    sources = []
                else:
                    response_text = result.get("message", "No response received")
                    sources = result.get("sources", [])
                    
                    # if result.get("metadata", {}).get("saved", False):
                    #     st.sidebar.success("✅ Chat saved to database!")
                    # else:
                    #     st.sidebar.warning("⚠️ Chat may not have been saved")
                
                st.markdown(response_text)

                if sources:
                    with st.expander("📚 Sources Used"):
                        for i, source in enumerate(sources, 1):
                            st.write(f"**{i}. {source['source_name']}** (similarity: {source['similarity']:.2f})")
                            st.write(f"_{source['content'][:200]}..._")
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response_text,
                "sources": sources
            })
        
        with st.sidebar:
            st.subheader("Chat Controls")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Clear Chat"):
                    st.session_state.messages = []
                    st.session_state.session_id = f"demo_{int(time.time())}"
                    st.rerun()
            
            with col2:
                if st.button("🔄 New Session"):
                    st.session_state.session_id = f"demo_{int(time.time())}"
                    st.success("New session started!")

            st.write(f"**Session ID:** {st.session_state.session_id}")
            st.write(f"**Messages:** {len(st.session_state.messages)}")
            
            # current_bot = next((bot for bot in bots_data if bot['id'] == selected_bot_id), None)
            # if current_bot:
            #     st.write("**Bot Configuration:**")
            #     st.write(f"- Model: {safe_get(current_bot, 'model', 'N/A')}")
            #     st.write(f"- Temperature: {safe_get(current_bot, 'temperature', 'N/A')}")
            #     st.write(f"- Top-K: {safe_get(current_bot, 'top_k', 'N/A')}")
        
        # st.info("💡 **Tip:** Upload documents in 'Document Management' first to get relevant answers!")

        doc_stats, _ = make_api_request("GET", "/api/v1/documents/stats", params={"bot_id": selected_bot_id})
        if doc_stats:
            completed_docs = safe_get(doc_stats.get('sources', {}), 'completed', 0)
            total_docs = safe_get(doc_stats.get('sources', {}), 'total', 0)
            
            # if total_docs == 0:
            #     st.warning("⚠️ No documents uploaded yet. Upload some documents to get meaningful responses!")
            # elif completed_docs < total_docs:
            #     st.warning(f"⚠️ {total_docs - completed_docs} documents still processing. Some answers may be incomplete.")
            # else:
            #     st.success(f"✅ {completed_docs} documents ready for chat!")

elif page == "Integration Setup":
    st.markdown('<div class="main-header"><h1>🔗 Integration Setup</h1></div>', unsafe_allow_html=True)
    
    bots_data, bots_error = make_api_request("GET", "/api/v1/bots/")
    
    if bots_error or not bots_data:
        st.error("No bots available. Create a bot first!")
        st.stop()
    
    selected_bot_id = st.selectbox("Select Bot for Integration", 
                                 options=[bot['id'] for bot in bots_data],
                                 format_func=lambda x: next((bot['name'] for bot in bots_data if bot['id'] == x), x))
    
    if selected_bot_id:
        tab1, tab2, tab3 = st.tabs(["📱 WhatsApp", "💬 Telegram", "📊 Integration Stats"])
        
        with tab1:
            st.subheader("📱 WhatsApp Business Integration")
            
            integrations_data, _ = make_api_request("GET", "/api/v1/integrations/", params={"bot_id": selected_bot_id, "platform": "whatsapp"})
            
            existing_whatsapp = None
            if integrations_data:
                for integration in integrations_data:
                    if integration['platform'] == 'whatsapp':
                        existing_whatsapp = integration
                        break
            
            if existing_whatsapp:
                st.success(f"WhatsApp integration exists (Active: {existing_whatsapp['is_active']})")
                
                config = existing_whatsapp['config']
                st.write("**Current Configuration:**")
                st.write(f"- Access Token: {'*' * 20}...{config.get('access_token', '')[-4:] if config.get('access_token') else 'Not set'}")
                st.write(f"- Phone Number ID: {config.get('phone_number_id', 'Not set')}")
                st.write(f"- Verify Token: {config.get('verify_token', 'Not set')}")
                
                if st.button("🔄 Toggle Active Status"):
                    update_data = {"is_active": not existing_whatsapp['is_active']}
                    result, error = make_api_request("PUT", f"/api/v1/integrations/{existing_whatsapp['id']}", update_data, params={"bot_id": selected_bot_id})
                    
                    if error:
                        st.error(f"Update failed: {error}")
                    else:
                        st.success("Integration status updated!")
                        st.rerun()
            
            else:
                st.info("No WhatsApp integration found. Create one below.")

            with st.form("whatsapp_form"):
                st.write("**WhatsApp Configuration:**")
                access_token = st.text_input("Access Token*", type="password", help="From Meta Developer Console")
                verify_token = st.text_input("Verify Token*", help="Custom token for webhook verification")
                phone_number_id = st.text_input("Phone Number ID*", help="From WhatsApp Business API")
                
                webhook_url = st.text_input("Webhook URL (auto-generated)", 
                                          value=f"https://a323e10366de.ngrok-free.app/api/v1/integrations/webhook/whatsapp/{selected_bot_id}",
                                          disabled=False)
                
                submitted = st.form_submit_button("💾 Save WhatsApp Config")
                
                if submitted:
                    if not access_token or not verify_token or not phone_number_id:
                        st.error("All fields are required!")
                    else:
                        config_data = {
                            "platform": "whatsapp",
                            "config": {
                                "access_token": access_token,
                                "verify_token": verify_token,
                                "phone_number_id": phone_number_id,
                                "webhook_url": webhook_url
                            }
                        }
                        
                        if existing_whatsapp:
                            result, error = make_api_request("PUT", f"/api/v1/integrations/{existing_whatsapp['id']}", 
                                                           {"config": config_data["config"]}, params={"bot_id": selected_bot_id})
                        else:
                            result, error = make_api_request("POST", "/api/v1/integrations/", config_data, params={"bot_id": selected_bot_id})
                        
                        if error:
                            st.error(f"Save failed: {error}")
                        else:
                            st.success("WhatsApp integration saved successfully!")
                            st.rerun()
            

            with st.expander("📖 WhatsApp Setup Instructions"):
                st.markdown("""
                **Steps to setup WhatsApp integration:**
                
                1. **Create Meta Developer Account**: Go to https://developers.facebook.com
                2. **Create App**: Create a new Business app
                3. **Add WhatsApp Product**: Add WhatsApp Business API to your app
                4. **Get Credentials**:
                   - Access Token from your app dashboard
                   - Phone Number ID from WhatsApp > Getting Started
                5. **Configure Webhook**: 
                   - Webhook URL: Use the auto-generated URL above
                   - Verify Token: Use the token you set above
                   - Subscribe to 'messages' events
                6. **Test**: Send a message to your WhatsApp number
                """)
        
        with tab2:
            st.subheader("💬 Telegram Bot Integration")
            
            integrations_data, _ = make_api_request("GET", "/api/v1/integrations/", params={"bot_id": selected_bot_id, "platform": "telegram"})
            
            existing_telegram = None
            if integrations_data:
                for integration in integrations_data:
                    if integration['platform'] == 'telegram':
                        existing_telegram = integration
                        break
            
            if existing_telegram:
                st.success(f"Telegram integration exists (Active: {existing_telegram['is_active']})")
                
                config = existing_telegram['config']
                st.write("**Current Configuration:**")
                st.write(f"- Bot Token: {'*' * 20}...{config.get('bot_token', '')[-4:] if config.get('bot_token') else 'Not set'}")
                
                if st.button("🔄 Toggle Telegram Status"):
                    update_data = {"is_active": not existing_telegram['is_active']}
                    result, error = make_api_request("PUT", f"/api/v1/integrations/{existing_telegram['id']}", update_data, params={"bot_id": selected_bot_id})
                    
                    if error:
                        st.error(f"Update failed: {error}")
                    else:
                        st.success("Telegram integration status updated!")
                        st.rerun()
            else:
                st.info("No Telegram integration found. Create one below.")
            
            with st.form("telegram_form"):
                st.write("**Telegram Configuration:**")
                bot_token = st.text_input("Bot Token*", type="password", help="From @BotFather")
                
                webhook_url = st.text_input("Webhook URL (auto-generated)", 
                                value=f"https://a323e10366de.ngrok-free.app/api/v1/integrations/webhook/telegram/{selected_bot_id}",
                                disabled=False)
                
                submitted = st.form_submit_button("💾 Save Telegram Config")
                
                if submitted:
                    if not bot_token:
                        st.error("Bot token is required!")
                    else:
                        config_data = {
                            "platform": "telegram",
                            "config": {
                                "bot_token": bot_token,
                                "webhook_url": webhook_url
                            }
                        }
                        
                        if existing_telegram:
                            result, error = make_api_request("PUT", f"/api/v1/integrations/{existing_telegram['id']}", 
                                                           {"config": config_data["config"]}, params={"bot_id": selected_bot_id})
                        else:
                            result, error = make_api_request("POST", "/api/v1/integrations/", config_data, params={"bot_id": selected_bot_id})
                        
                        if error:
                            st.error(f"Save failed: {error}")
                        else:
                            st.success("Telegram integration saved successfully!")
                            
                            if result:
                                integration_id = result.get('id') or existing_telegram['id']
                                webhook_result, webhook_error = make_api_request("POST", f"/api/v1/integrations/{integration_id}/webhook/setup", 
                                                                               params={"bot_id": selected_bot_id, "webhook_url": webhook_url})
                                if webhook_error:
                                    st.warning(f"Webhook setup failed: {webhook_error}")
                                else:
                                    st.success("Webhook configured automatically!")
                            
                            st.rerun()
            
            with st.expander("📖 Telegram Setup Instructions"):
                st.markdown("""
                **Steps to setup Telegram integration:**
                
                1. **Create Bot**: Message @BotFather on Telegram
                2. **Use /newbot command**: Follow instructions to create new bot
                3. **Get Token**: Copy the bot token provided by BotFather
                4. **Paste Token**: Enter the token in the form above
                5. **Auto-webhook**: Webhook will be configured automatically
                6. **Test**: Send a message to your bot on Telegram
                """)
        
        with tab3:
            st.subheader("📊 Integration Statistics")

            overview_data, overview_error = make_api_request("GET", "/api/v1/integrations/stats/overview", params={"bot_id": selected_bot_id})
            
            if overview_error:
                st.error(f"Failed to load statistics: {overview_error}")
            elif overview_data:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Integrations", overview_data.get('total_integrations', 0))
                with col2:
                    st.metric("Active Integrations", overview_data.get('active_integrations', 0))
                with col3:
                    total_messages = sum(platform.get('total_messages', 0) for platform in overview_data.get('platforms', {}).values())
                    st.metric("Total Messages", total_messages)
                
                platforms = overview_data.get('platforms', {})
                if platforms:
                    st.subheader("Platform Statistics")
                    
                    for platform_name, platform_data in platforms.items():
                        with st.expander(f"{platform_name.title()} Statistics"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Total Messages:** {platform_data.get('total_messages', 0)}")
                                st.write(f"**Unique Users:** {platform_data.get('unique_users', 0)}")
                                st.write(f"**Messages Today:** {platform_data.get('messages_today', 0)}")
                            
                            with col2:
                                st.write(f"**Status:** {platform_data.get('status', 'Unknown')}")
                                st.write(f"**Active:** {'Yes' if platform_data.get('is_active') else 'No'}")
                                if platform_data.get('last_activity'):
                                    st.write(f"**Last Activity:** {pd.to_datetime(platform_data['last_activity']).strftime('%Y-%m-%d %H:%M')}")

elif page == "Analytics":
    st.markdown('<div class="main-header"><h1>📈 Analytics</h1></div>', unsafe_allow_html=True)
    
    bots_data, bots_error = make_api_request("GET", "/api/v1/bots/")
    
    if bots_error or not bots_data:
        st.error("No bots available for analytics!")
        st.stop()
    
    selected_bot_id = st.selectbox("Select Bot for Analytics", 
                                 options=[bot['id'] for bot in bots_data],
                                 format_func=lambda x: next((bot['name'] for bot in bots_data if bot['id'] == x), x))
    
    if selected_bot_id:
        bot_stats, _ = make_api_request("GET", f"/api/v1/bots/{selected_bot_id}/stats")
        chat_stats, _ = make_api_request("GET", "/api/v1/chat/stats", params={"bot_id": selected_bot_id})
        doc_stats, doc_stats_error = make_api_request("GET", "/api/v1/documents/stats", params={"bot_id": selected_bot_id})
        integration_overview, _ = make_api_request("GET", "/api/v1/integrations/stats/overview", params={"bot_id": selected_bot_id})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Chats", chat_stats.get('total_messages', 0) if chat_stats else 0)
        with col2:
            st.metric("Unique Users", chat_stats.get('unique_users', 0) if chat_stats else 0)
        with col3:
            if doc_stats_error:
                st.metric("Documents", "Error")
            else:
                st.metric("Documents", safe_get(doc_stats.get('documents', {}), 'total', 0) if doc_stats else 0)
        with col4:
            st.metric("Active Integrations", integration_overview.get('active_integrations', 0) if integration_overview else 0)
        
        if chat_stats:
            platform_dist = chat_stats.get('platform_distribution', {})
            if platform_dist:
                st.subheader("📊 Chat Distribution by Platform")
                
                df_platform = pd.DataFrame(list(platform_dist.items()), columns=['Platform', 'Messages'])
                fig_platform = px.pie(df_platform, values='Messages', names='Platform', title="Messages by Platform")
                st.plotly_chart(fig_platform, use_container_width=True)
        
        if doc_stats and not doc_stats_error:
            sources_stats = doc_stats.get('sources', {})
            if sources_stats:
                st.subheader("📁 Document Processing Status")
                
                status_data = {
                    'Status': ['Completed', 'Processing', 'Failed'],
                    'Count': [
                        sources_stats.get('completed', 0),
                        sources_stats.get('processing', 0), 
                        sources_stats.get('failed', 0)
                    ]
                }
                
                df_status = pd.DataFrame(status_data)
                fig_status = px.bar(df_status, x='Status', y='Count', title="Document Processing Status")
                st.plotly_chart(fig_status, use_container_width=True)
        elif doc_stats_error:
            st.warning(f"Could not load document statistics: {doc_stats_error}")

        st.subheader("🕒 Recent Activity")
        
        if chat_stats:
            st.write(f"**Recent Activity (24h):** {chat_stats.get('recent_activity_24h', 0)} messages")
        
        chat_history, _ = make_api_request("GET", "/api/v1/chat/history", params={"bot_id": selected_bot_id, "limit": 10})
        
        if chat_history:
            st.subheader("💬 Recent Conversations")
            
            df_chat = pd.DataFrame(chat_history)
            df_chat['createdAt'] = pd.to_datetime(df_chat['createdAt']).dt.strftime('%Y-%m-%d %H:%M')
            
            for _, chat in df_chat.iterrows():
                with st.expander(f"💬 {chat['user_id']} - {chat['createdAt']}"):
                    st.write(f"**User:** {chat['human_message']}")
                    st.write(f"**Bot:** {chat['ai_message']}")
                    if chat.get('platform'):
                        st.write(f"**Platform:** {chat['platform']}")
import streamlit as st
import numpy as np
from pypdf import PdfReader

import os
from dotenv import load_dotenv
from fastembed import TextEmbedding
from groq import Groq

def split_text_into_chunks(text, chunk_size=1000, overlap=200):
    chunks = []
    for page_number, text in page_texts:
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "page": page_number
                })

            start += chunk_size - overlap

    return chunks

@st.cache_data(show_spinner="Creating PDF embeddings...")
def get_chunk_embeddings(chunks):
    vectors = list(embedding_model.embed(chunk["text"] for chunk in chunks))
    return np.array(vectors)

def find_relevant_chunks(question, chunks, embedding_model, top_k=3):
        if not chunks:
         return []

        chunk_embeddings = get_chunk_embeddings(chunks)

        question_embedding = np.array(
           list(embedding_model.query_embed(question))
        )[0]

        # Cosine similarity calculate karo
        chunk_norms = np.linalg.norm(chunk_embeddings, axis=1)
        question_norm = np.linalg.norm(question_embedding)
    
        scores = (
            chunk_embeddings @ question_embedding
      ) / (chunk_norms * question_norm + 1e-10)

        top_indices = np.argsort(scores)[::-1][:top_k]

        return [chunks[i] for i in top_indices]

st.set_page_config(
    page_title="DocuMind AI",
    page_icon="📚",
    layout="wide"
)

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("NO API key fouond.")
    st.stop()

client = Groq(api_key=api_key)
embedding_model = TextEmbedding()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("📚 DocuMind AI")
st.subheader("Your AI-Powered PDF Research Assistant")

st.write(
    "Upload a PDF and explore its content with AI."
)

uploaded_file = st.file_uploader(
    "Choose a PDF file.",
    type=["pdf"]
)

if uploaded_file is not None:
    reader = PdfReader(uploaded_file)

    text = ""
    page_texts = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""

        if page_text.strip():
            text += page_text + "\n"
            page_texts.append((page_number, page_text))

    chunks = split_text_into_chunks(text)

    st.write("**Total chunks:**", len(chunks)) 

    st.success("PDF uploaded successfully")

    st.write("**File name:**", uploaded_file.name)
    st.write("**Total pages**", len(reader.pages))
    st.write("**Extracted characters:**", len(text))

    with st.expander("Preview extracted text"):
        
        st.text(text[:3000])

    with st.expander("Preview first text chunk"):

        if chunks:
            st.text(chunks[0]["text"])
        else:
            st.warning("No readable text found in this PDF.")
                    
    st.divider()
    st.subheader(" = PDF Summary")

    if st.button("Symmarize PDF"):
        if not text.strip():
            st.warning("NO Redable text extract from this PDF")
        else:
            with st.spinner("Generating PDF summary "):
                try:
                    summary_response = client.chat.completions.create(
                        model="qwen/qwen3.8-27b",
                        messages=[
                            {
                                "role": "system",
                                "content": ( 
                                    "You are a helpful research assistant."
                                    "Summarize the provided PDF text in simple"
                                    "language. Inckude the main topic, key points,"
                                    "and important conclusions. Do no invent facts."
                                )
                            },
                            {
                                "role": "user",
                                "content": (
                                    "Summarize this PDF text:\n\n"
                                    + text[:8000]
                                )
                            }
                        ],
                        temperature=0.2
                    )

                    summary =  summary_response.choices[0].message.content

                    st.markdown("### 📝 Summary")
                    st.write(summary)
                except Exception as e:
                    st.error(f"Summary error: {e}")

    st.divider()
    st.subheader("Ask questions about your PDF")

    question = st.text_input(
        "Enter your question about the uploaded PDF:"
    )

    if st.button("Ask AI"):
        if not text.strip():
            st.warning("No relatable text asked from this PDF.")
        elif not question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Finding relevant text and generating answer..."):
                try:
                    relevant_chunks = find_relevant_chunks(
                        question,
                        chunks,
                        embedding_model,
                        top_k=3
                    )

                    if not relevant_chunks:
                        st.warning("NO relevant text chunks found.")

                    else:
                        context = "\n\n---\n\n".join(
                            f"Page {chunk['page']}:\n{chunk['text']}"
                            for chunk in relevant_chunks
                        )


                    st.write("**Relevant chunks found:**", len(relevant_chunks))


                    response = client.chat.completions.create(
                        model="qwen/qwen3.8-27b",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "Answer the user's question using only "
                                    "the provided PDF text. If the answer "
                                    "is not present, say you could not find "
                                    "it in the PDF."
                                )
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Relevant PDF excerpts:\n{context}\n\n"
                                    f"Question: {question}"
                                )
                            }
                        ],
                        temperature=0.2
                    )

                    answer = response.choices[0].message.content

                    st.session_state.chat_history.append({
                        "question": question,
                        "answer": answer
                    })


                    st.subheader("Answer")
                    st.write(answer)

                    with st.expander("View relevant chunks used"):
                            for i, chunk in enumerate(relevant_chunks, start=1):
                                st.markdown(f"**Chunk {i}**")
                                st.write(chunk["text"])
                                st.caption(f"Source: PDF page {chunk['page']}")

                except Exception as e:
                    st.error(f"Groq API error: {e}")

    st.divider()
    st.subheader("💬 Chat History")

    if st.session_state.chat_history:
        for i, chat in enumerate(st.session_state.chat_history, start=1):
            with st.expander(f"Question {i}: {chat['question']}"):
                st.markdown("**Question:**")
                st.write(chat["question"])

                st.markdown("**Answer:**")
                st.write(chat["answer"])
        if st.button("Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()
    else:
        st.info("NO History found. Ask questions about PDF.")




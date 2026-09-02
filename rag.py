import base64
import hashlib
import os
import re
import time
import uuid
import gradio as gr

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from openai import OpenAI
from dotenv import load_dotenv

MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "20"))
MIN_SECONDS_BETWEEN_CHATS = float(os.getenv("MIN_SECONDS_BETWEEN_CHATS", "2"))
_last_chat_time = 0.0


def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', name).strip('._-')
    return sanitized if sanitized else "doc"


def _file_content_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def get_or_create_vectorstore(file_path: str):
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    base_name = _sanitize_name(file_name)[:40]
    content_hash = _file_content_hash(file_path)
    # Namespacing by content hash (not just filename) keeps two different
    # files that share a name — or a re-edited file with the same name —
    # from colliding in the same Chroma collection.
    collection_name = f"{base_name}_{content_hash}"
    if len(collection_name) < 3:
        collection_name = collection_name + '_col'
    vectorstore = Chroma(
        persist_directory="./data",
        collection_name=collection_name,
        embedding_function=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    )
    return vectorstore


def read_pdf_content(file_path: str | None):
    if file_path is None:
        return None
    loader = PyMuPDFLoader(file_path)
    return loader.load()


def chunk_document(documents, source_id: str):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=80,
    )
    chunks = text_splitter.split_documents(documents)
    for index, chunk in enumerate(chunks):
        # Include source_id + index so repeated boilerplate text (headers,
        # footers, etc.) doesn't collide onto the same chunk id and get
        # silently dropped by Chroma's upsert-by-id behavior.
        chunk.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}:{index}:{chunk.page_content}"))
    return chunks


def create_pdf_html(file_path: str | None):
    if file_path is None:
        return ""
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        return f'''
            <div style="width: 100%; height: 800px;">
                <iframe
                    src="data:application/pdf;base64,{base64_pdf}"
                    width="100%"
                    height="100%"
                    style="border: none;">
                </iframe>
            </div>
        '''
    except Exception as e:
        return f"Error displaying PDF: {str(e)}"


def process_file(file_path: str | None):
    if file_path is None:
        yield "Please upload a PDF file first.", ""
        return

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        yield (
            f"File is too large ({file_size_mb:.1f} MB). "
            f"Maximum allowed size is {MAX_FILE_SIZE_MB:.0f} MB.",
            "",
        )
        return

    try:
        yield "Reading PDF file...", ""
        pdf_html = create_pdf_html(file_path)
        yield "Processing PDF file...", pdf_html

        documents = read_pdf_content(file_path)
        if not documents:
            yield "Error processing PDF file.", ""
            return

        chunks = chunk_document(documents, source_id=os.path.basename(file_path))

        yield "Creating vector store...", pdf_html
        vectorstore = get_or_create_vectorstore(file_path)
        yield "Adding documents to vector store...", pdf_html
        vectorstore.add_documents(chunks)

        yield "PDF file processed successfully.", pdf_html
    except Exception as e:
        yield f"Error processing file: {str(e)}", ""


load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if OPENAI_API_KEY is None:
    raise ValueError(
        "Please set the OPENAI_API_KEY environment variable. You can get one at https://platform.openai.com/account/api-keys")
openai_client = OpenAI(api_key=OPENAI_API_KEY)


def chat_with_pdf(file_path: str | None, message: str, history):
    global _last_chat_time

    if not message:
        yield "", history
        return

    if not file_path:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "Please upload and process a PDF file first."})
        yield "", history
        return

    now = time.monotonic()
    if now - _last_chat_time < MIN_SECONDS_BETWEEN_CHATS:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "You're sending messages too quickly — please wait a moment and try again."})
        yield "", history
        return
    _last_chat_time = now

    try:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "Processing..."})
        yield "", history

        vectorstore = get_or_create_vectorstore(file_path)
        results = vectorstore.similarity_search(query=message, k=3)

        if not results:
            history[-1] = {"role": "assistant", "content": "No relevant data found in the PDF."}
            yield "", history
            return

        history[-1] = {"role": "assistant", "content": "Data found in VectorDB!"}
        yield "", history

        CONTEXT = ""
        for document in results:
            CONTEXT += document.page_content + "\n\n"

        prompt = f"""
        Use the following CONTEXT to answer the QUESTION at the end.
        If you don't know the answer or unsure of the answer, just say that you don't know, don't try to make up an answer.
        Use an unbiased and journalistic tone.

        CONTEXT: {CONTEXT}
        QUESTION: {message}
        """

        print(prompt)
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        print(response.choices[0].message.content)

        history[-1] = {"role": "assistant", "content": response.choices[0].message.content}
        yield "", history
    except Exception as e:
        print('error', e)
        history.append({"role": "assistant", "content": f"Error: {str(e)}"})
        yield "", history


def create_ui():
    with gr.Blocks() as demo:
        gr.Markdown("# Chat with PDF")

        with gr.Row():
            with gr.Column(scale=1):
                file_input = gr.File(
                    label="Upload PDF",
                    file_types=[".pdf"],
                )
                process_button = gr.Button("Process PDF")
                status_output = gr.Textbox(label="Status")
                pdf_preview = gr.HTML(label="PDF Preview")

            with gr.Column(scale=1):
                chatbot = gr.Chatbot(height=450)
                message_box = gr.Textbox(label="Ask a question about your PDF")
                submit_btn = gr.Button("Chat", variant="primary")

        process_button.click(
            fn=process_file,
            inputs=[file_input],
            outputs=[status_output, pdf_preview]
        )

        message_box.submit(
            fn=chat_with_pdf,
            inputs=[file_input, message_box, chatbot],
            outputs=[message_box, chatbot]
        )

        submit_btn.click(
            fn=chat_with_pdf,
            inputs=[file_input, message_box, chatbot],
            outputs=[message_box, chatbot]
        )

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch()

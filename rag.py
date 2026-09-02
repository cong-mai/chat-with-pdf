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
        yield "Add a PDF before reading.", ""
        return

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        yield (
            f"That file is too large ({file_size_mb:.1f} MB). "
            f"The limit is {MAX_FILE_SIZE_MB:.0f} MB.",
            "",
        )
        return

    try:
        yield "Opening the file…", ""
        pdf_html = create_pdf_html(file_path)
        yield "Reading through it…", pdf_html

        documents = read_pdf_content(file_path)
        if not documents:
            yield "Couldn't read that file.", ""
            return

        chunks = chunk_document(documents, source_id=os.path.basename(file_path))

        yield "Building the index…", pdf_html
        vectorstore = get_or_create_vectorstore(file_path)
        yield "Filing the pages…", pdf_html
        vectorstore.add_documents(chunks)

        yield "Ready. Ask away.", pdf_html
    except Exception as e:
        yield f"Couldn't read that file: {str(e)}", ""


load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if OPENAI_API_KEY is None:
    raise ValueError(
        "Please set the OPENAI_API_KEY environment variable. You can get one at https://platform.openai.com/account/api-keys")
openai_client = OpenAI(api_key=OPENAI_API_KEY)


def _entry(role: str, content: str) -> dict:
    # Prefixing the actual message content (rather than styling it in via
    # CSS) keeps the Q/A marker legible even if the chatbot's internal
    # markup changes between Gradio versions.
    prefix = "Q  " if role == "user" else "A  "
    return {"role": role, "content": f"{prefix}{content}"}


def chat_with_pdf(file_path: str | None, message: str, history):
    global _last_chat_time

    if not message:
        yield "", history
        return

    if not file_path:
        history.append(_entry("user", message))
        history.append(_entry("assistant", "Add and read a PDF before asking questions."))
        yield "", history
        return

    now = time.monotonic()
    if now - _last_chat_time < MIN_SECONDS_BETWEEN_CHATS:
        history.append(_entry("user", message))
        history.append(_entry("assistant", "Give it a moment before asking again."))
        yield "", history
        return
    _last_chat_time = now

    try:
        history.append(_entry("user", message))
        history.append(_entry("assistant", "Reading through the document…"))
        yield "", history

        vectorstore = get_or_create_vectorstore(file_path)
        results = vectorstore.similarity_search(query=message, k=3)

        if not results:
            history[-1] = _entry("assistant", "Nothing in the document answers that.")
            yield "", history
            return

        history[-1] = _entry("assistant", "Found the relevant passage…")
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

        history[-1] = _entry("assistant", response.choices[0].message.content)
        yield "", history
    except Exception as e:
        print('error', e)
        history.append(_entry("assistant", f"Something went wrong: {str(e)}"))
        yield "", history


# "Reading Room" theme — a two-pane reading desk (document + notes) styled
# like paper and ledger rules rather than the rounded-card/shadow SaaS kit.
# Palette: Ledger #E3DECD (page), Card #FBF9F2 (surfaces), Ink #23281F
# (text), Pencil #A8332E (primary action), Stamp #2E4A5E (focus/links),
# Rule #C7BFA4 (hairlines).
THEME = gr.themes.Base(
    font=[gr.themes.GoogleFont("IBM Plex Sans"), "sans-serif"],
    font_mono=[gr.themes.GoogleFont("IBM Plex Mono"), "monospace"],
    radius_size=gr.themes.sizes.radius_sm,
).set(
    body_background_fill="#E3DECD",
    background_fill_primary="#FBF9F2",
    background_fill_secondary="#FBF9F2",
    border_color_primary="#C7BFA4",
    block_background_fill="#FBF9F2",
    block_border_color="#C7BFA4",
    block_label_text_color="#23281F",
    body_text_color="#23281F",
    button_primary_background_fill="#A8332E",
    button_primary_background_fill_hover="#8C2A26",
    button_primary_text_color="#FBF9F2",
    button_secondary_background_fill="#FBF9F2",
    button_secondary_border_color="#C7BFA4",
    button_secondary_text_color="#23281F",
    input_background_fill="#FBF9F2",
    input_border_color="#C7BFA4",
    block_radius="3px",
    button_large_radius="3px",
    button_small_radius="3px",
    input_radius="3px",
)

HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@1,500&display=swap" rel="stylesheet">
"""

CSS = """
#header .headline {
    font-family: 'Newsreader', serif;
    font-style: italic;
    font-weight: 500;
    font-size: 2.25rem;
    color: #23281F;
    margin: 0 0 0.2em 0;
    text-align: left;
}
#header .subline {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 1rem;
    color: #55503f;
    margin: 0 0 1.5rem 0;
    text-align: left;
}
#notes-pane {
    border-left: 1px solid #C7BFA4;
    padding-left: 1.5rem !important;
}
#chatbot {
    --radius-md: 3px;
    --shadow-drop: none;
    --color-accent-soft: #FBF9F2;
}
#chatbot .bot-row, #chatbot .user-row {
    background: transparent !important;
    box-shadow: none !important;
}
#chatbot .message-row {
    border-bottom: 1px solid #C7BFA4;
    padding-bottom: 0.75rem;
    margin-bottom: 0.75rem;
}
#chatbot .message-row:last-child {
    border-bottom: none;
}
#chatbot .user, #chatbot .user *,
#chatbot .bot, #chatbot .bot * {
    text-align: left !important;
}
.gradio-container button:focus-visible,
.gradio-container input:focus-visible,
.gradio-container textarea:focus-visible {
    outline: 2px solid #2E4A5E !important;
    outline-offset: 1px;
}
"""


def create_ui():
    with gr.Blocks() as demo:
        with gr.Column(elem_id="header"):
            gr.HTML(
                '<div class="headline">Read together.</div>'
                '<div class="subline">Ask your document things.</div>'
            )

        with gr.Row():
            with gr.Column(scale=1, elem_id="doc-pane"):
                file_input = gr.File(
                    label="Add a PDF",
                    file_types=[".pdf"],
                )
                process_button = gr.Button("Read this PDF")
                status_output = gr.Textbox(label="Status", interactive=False)
                pdf_preview = gr.HTML(label="Preview")

            with gr.Column(scale=1, elem_id="notes-pane"):
                chatbot = gr.Chatbot(height=450, elem_id="chatbot", layout="panel")
                message_box = gr.Textbox(label="Ask something about the document")
                submit_btn = gr.Button("Ask", variant="primary")

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
    demo.launch(theme=THEME, css=CSS, head=HEAD)

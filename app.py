"""Gradio interface for the grounded RAG assistant."""

from __future__ import annotations

import os

import gradio as gr

from query import ask
from rebuild_index import rebuild_index


def format_sources(source_items):
    """Format retrieved source strings for the side panel."""
    if not source_items:
        return "No sources returned."
    return "\n".join(f"• {source}" for source in source_items)


def handle_query(question, history):
    """Run a user question through the RAG pipeline and update chat history."""
    history = history or []
    if not question or not question.strip():
        return history, "", "Enter a question first."

    history = [*history, {"role": "user", "content": question.strip()}]
    try:
        result = ask(question)
        answer = str(result["answer"])
        sources = format_sources(result["sources"])
    except Exception as error:
        answer = f"Error: {error}"
        sources = ""

    history.append({"role": "assistant", "content": answer})
    return history, "", sources


def clear_chat():
    """Clear the conversation and source panel."""
    return [], ""


def handle_rebuild_index():
    """Rebuild the local ChromaDB index and return a UI status message."""
    try:
        report = rebuild_index()
    except Exception as error:
        return f"Index rebuild failed: {error}"

    return (
        "Index rebuilt successfully.\n"
        f"Indexed chunks: {report['indexed_count']}\n"
        f"Supported files: {report['supported_files']}\n"
        f"Skipped files: {report['skipped_files']}\n"
        f"Collection: {report['persist_dir']}/{report['collection_name']}"
    )


theme = gr.themes.Soft(
    primary_hue="sky",
    neutral_hue="slate",
    radius_size="sm",
)

css = """
.gradio-container {
  background: #1f2937;
  color: #f8fafc;
}
.app-wrap {
  max-width: 1040px;
  min-height: calc(100vh - 32px);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}
.title {
  padding: 18px 0 10px;
  text-align: center;
}
.title h1 {
  font-size: 24px;
  font-weight: 650;
  margin: 0;
  color: #f8fafc;
}
.chatbot {
  flex: 1;
  border: 1px solid #94a3b8;
  border-radius: 8px;
  background: #111827;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.32), 0 18px 42px rgba(15, 23, 42, 0.34);
}
.chatbot .message {
  border: 1px solid rgba(148, 163, 184, 0.32);
}
.source-box textarea,
.composer textarea {
  border: 1px solid #93c5fd !important;
  background: #f8fafc !important;
  color: #0f172a !important;
}
.source-box textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 13px !important;
}
.composer textarea {
  font-size: 15px !important;
  border-radius: 8px !important;
}
button.primary,
.primary > button {
  background: #7dd3fc !important;
  border-color: #38bdf8 !important;
  color: #082f49 !important;
}
button.primary:hover,
.primary > button:hover {
  background: #bae6fd !important;
  border-color: #7dd3fc !important;
}
"""

with gr.Blocks(title="GMU Opportunities Guide") as demo:
    with gr.Column(elem_classes=["app-wrap"]):
        gr.Markdown(
            """
            <div class="title">
              <h1>GMU Opportunities Guide</h1>
            </div>
            """
        )
        chatbot = gr.Chatbot(
            label="Conversation",
            height=560,
            show_label=False,
            elem_classes=["chatbot"],
            layout="bubble",
        )
        with gr.Row(equal_height=True):
            inp = gr.Textbox(
                label="Message",
                placeholder="Ask about GMU opportunities...",
                lines=2,
                scale=8,
                elem_classes=["composer"],
            )
            btn = gr.Button("Ask", variant="primary", scale=1)
        with gr.Accordion("Retrieved sources", open=True):
            sources = gr.Textbox(
                label="Retrieved from",
                lines=6,
                show_label=False,
                elem_classes=["source-box"],
            )
        with gr.Row():
            rebuild = gr.Button("Rebuild Index", variant="secondary")
            clear = gr.Button("Clear", variant="secondary")

        btn.click(handle_query, inputs=[inp, chatbot], outputs=[chatbot, inp, sources])
        inp.submit(handle_query, inputs=[inp, chatbot], outputs=[chatbot, inp, sources])
        rebuild.click(handle_rebuild_index, outputs=sources)
        clear.click(clear_chat, outputs=[chatbot, sources])


if __name__ == "__main__":
    server_name = os.getenv("GRADIO_SERVER_NAME", "localhost")
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    demo.launch(server_name=server_name, server_port=server_port, theme=theme, css=css)

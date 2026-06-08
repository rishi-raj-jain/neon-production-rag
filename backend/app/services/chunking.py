from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_markdown(text: str, *, source_id: str, title: str) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=150,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )
    parts = splitter.split_text(text)
    chunks: list[dict] = []
    for index, content in enumerate(parts):
        cleaned = content.strip()
        if len(cleaned) < 80:
            continue
        chunks.append(
            {
                "index": index,
                "content": cleaned,
                "metadata": {
                    "source_id": source_id,
                    "title": title,
                    "chunk_index": index,
                },
            }
        )
    return chunks

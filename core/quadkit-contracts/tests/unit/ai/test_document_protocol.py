"""Tests for Document and Splitter contracts."""
from __future__ import annotations


def test_document():
    """Document should have page_content and metadata."""
    from quadkit.contracts.ai.document import Document
    
    doc = Document(page_content="Hello world", metadata={"source": "test"})
    assert doc.page_content == "Hello world"
    assert doc.metadata["source"] == "test"


def test_text_splitter():
    """TextSplitter should split text into chunks."""
    from quadkit.contracts.ai.document import TextSplitter
    
    splitter = TextSplitter(chunk_size=5, chunk_overlap=1)
    text = "Hello world this is a test"
    chunks = splitter.split_text(text)
    assert len(chunks) > 1


def test_recursive_character_text_splitter():
    """RecursiveCharacterTextSplitter should split by characters."""
    from quadkit.contracts.ai.document import RecursiveCharacterTextSplitter
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=2)
    text = "Hello\nworld\r\ntest"
    chunks = splitter.split_text(text)
    assert len(chunks) > 0

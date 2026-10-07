"""Ядро RAG-бота: поиск по FAISS-индексу + промптинг + LLM."""

from .pipeline import PIPELINE, Answer, RAGPipeline

__all__ = ["PIPELINE", "Answer", "RAGPipeline"]

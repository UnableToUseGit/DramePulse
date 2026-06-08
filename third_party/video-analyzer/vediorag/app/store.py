from llama_index.core import Settings as LlamaSettings
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

from .config import Settings


def configure_llama_index(settings: Settings) -> None:
    LlamaSettings.llm = OpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        api_base=settings.openai_api_base,
    )
    LlamaSettings.embed_model = OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        api_base=settings.openai_api_base,
    )


def get_chroma_collection(settings: Settings):
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return client.get_or_create_collection(settings.chroma_collection)


def get_index(settings: Settings) -> VectorStoreIndex:
    configure_llama_index(settings)
    vector_store = ChromaVectorStore(chroma_collection=get_chroma_collection(settings))
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

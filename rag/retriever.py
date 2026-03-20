import os
import hashlib
import chromadb
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

class CodeRetriever:
    def __init__(self, persist_dir="~/.Tangi/code_index"):
        self.persist_dir = os.path.expanduser(persist_dir)
        
        # Load the same model as indexer
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        cache_path = os.path.expanduser("~/.cache/huggingface/hub")
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            local_files_only=True,
            cache_dir=cache_path
        )
        self.model = AutoModel.from_pretrained(
            model_name,
            local_files_only=True,
            cache_dir=cache_path
        )
        
        self.client = chromadb.PersistentClient(path=self.persist_dir)
    
    def encode(self, texts):
        """Convert texts to embeddings"""
        if isinstance(texts, str):
            texts = [texts]
            
        # Tokenize
        inputs = self.tokenizer(
            texts, 
            padding=True, 
            truncation=True, 
            return_tensors="pt", 
            max_length=512
        )
        
        # Generate embeddings
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use mean pooling for sentence embeddings
            embeddings = outputs.last_hidden_state.mean(dim=1).numpy()
        
        return embeddings
    
    def retrieve(self, directory, query, n_results=5):
        """Find relevant code chunks for a query"""
        collection_name = hashlib.md5(os.path.expanduser(directory).encode()).hexdigest()[:10]
        
        try:
            collection = self.client.get_collection(collection_name)
            count = collection.count()
            
            if count == 0:
                return []
                
        except Exception as e:
            return []
        
        # Encode query
        query_embedding = self.encode([query]).tolist()
        
        # Search
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Format results
        chunks = []
        for i in range(len(results['ids'][0])):
            chunks.append({
                'text': results['documents'][0][i],
                'file': results['metadatas'][0][i]['file'],
                'start_line': results['metadatas'][0][i]['start_line'],
                'end_line': results['metadatas'][0][i]['end_line'],
                'relevance': 1 - results['distances'][0][i]
            })
        
        return chunks
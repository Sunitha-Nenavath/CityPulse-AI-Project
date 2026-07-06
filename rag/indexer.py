import os
import pickle
import numpy as np
import pandas as pd

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSIFIED_DATA_PATH = os.path.join(BASE_DIR, "data", "classified_complaints.csv")
RAG_DIR = os.path.join(BASE_DIR, "data")
FAISS_INDEX_PATH = os.path.join(RAG_DIR, "faiss_index.bin")
RESOLVED_META_PATH = os.path.join(RAG_DIR, "resolved_metadata.csv")
FALLBACK_INDEX_PATH = os.path.join(RAG_DIR, "fallback_rag.pkl")

class CivicRAG:
    def __init__(self):
        self.resolved_df = None
        self.engine_type = None  # 'faiss', 'tfidf', or 'pure_python'
        self.encoder = None
        self.index = None
        self.vectorizer = None
        self.tfidf_matrix = None
        
    def build_index(self):
        """
        Loads classified complaints, filters resolved ones, and builds the search index.
        """
        print("Building RAG Index...")
        if not os.path.exists(CLASSIFIED_DATA_PATH):
            print(f"Error: Classified complaints dataset not found at {CLASSIFIED_DATA_PATH}.")
            return False
            
        df = pd.read_csv(CLASSIFIED_DATA_PATH)
        # Filter for resolved complaints that have description and resolution notes
        self.resolved_df = df[
            (df["status"] == "resolved") & 
            (df["description_text"].notna()) & 
            (df["resolution_notes"].notna())
        ].copy().reset_index(drop=True)
        
        if len(self.resolved_df) == 0:
            print("Warning: No resolved complaints found to index.")
            return False
            
        print(f"Found {len(self.resolved_df)} resolved complaints for indexing.")
        
        # Prepare combined search text
        self.resolved_df["search_text"] = (
            "Description: " + self.resolved_df["description_text"] + 
            " | Resolution: " + self.resolved_df["resolution_notes"]
        )
        
        # Try to use FAISS + sentence-transformers
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            print("Attempting to build FAISS index...")
            
            # Load model
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
            texts = self.resolved_df["search_text"].tolist()
            
            # Generate embeddings
            embeddings = self.encoder.encode(texts, show_progress_bar=True, batch_size=128)
            embeddings = np.array(embeddings).astype("float32")
            
            # L2 normalization for Cosine Similarity using Inner Product
            faiss.normalize_L2(embeddings)
            
            # IndexFlatIP is Inner Product (which is Cosine Similarity after normalization)
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)
            self.index.add(embeddings)
            
            # Save files
            faiss.write_index(self.index, FAISS_INDEX_PATH)
            self.resolved_df.to_csv(RESOLVED_META_PATH, index=False)
            self.engine_type = "faiss"
            
            # Save metadata about engine
            with open(os.path.join(RAG_DIR, "rag_config.pkl"), "wb") as f:
                pickle.dump({"engine_type": "faiss"}, f)
                
            print("FAISS Index built and saved successfully!")
            return True
            
        except Exception as e:
            print(f"FAISS/SentenceTransformers not available or failed: {e}. Trying scikit-learn TF-IDF fallback...")
            
        # Try scikit-learn TF-IDF fallback
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            print("Building TF-IDF Index using scikit-learn...")
            
            texts = self.resolved_df["search_text"].tolist()
            self.vectorizer = TfidfVectorizer(stop_words="english", max_features=10000)
            self.tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # Save fallback index
            with open(FALLBACK_INDEX_PATH, "wb") as f:
                pickle.dump({
                    "vectorizer": self.vectorizer,
                    "tfidf_matrix": self.tfidf_matrix,
                    "resolved_df": self.resolved_df,
                    "engine_type": "tfidf"
                }, f)
                
            # Save metadata about engine
            with open(os.path.join(RAG_DIR, "rag_config.pkl"), "wb") as f:
                pickle.dump({"engine_type": "tfidf"}, f)
                
            self.engine_type = "tfidf"
            print("TF-IDF Index built and saved successfully!")
            return True
            
        except Exception as e:
            print(f"scikit-learn TF-IDF failed: {e}. Building Pure-Python TF-IDF index...")
            
        # Pure-Python TF-IDF Fallback
        self.build_pure_python_index()
        return True

    def build_pure_python_index(self):
        """
        Completely dependency-free custom indexer based on simple term frequencies.
        """
        import re
        from collections import Counter
        
        texts = self.resolved_df["search_text"].tolist()
        
        # Tokenize and clean helper
        def tokenize(text):
            return re.findall(r'\w+', text.lower())
            
        # Build vocabulary and doc frequencies
        vocab = set()
        doc_counts = []
        for txt in texts:
            tokens = tokenize(txt)
            doc_counts.append(Counter(tokens))
            vocab.update(tokens)
            
        vocab = list(vocab)
        vocab_index = {word: i for i, word in enumerate(vocab)}
        
        # Calculate IDF
        num_docs = len(texts)
        df_counts = Counter()
        for counter in doc_counts:
            for word in counter:
                df_counts[word] += 1
                
        idf = {}
        for word in vocab:
            # Standard smooth idf
            idf[word] = np.log((1 + num_docs) / (1 + df_counts[word])) + 1
            
        # Generate raw sparse TF-IDF representations
        tfidf_vectors = []
        for counter in doc_counts:
            vec = {}
            for word, count in counter.items():
                # tf * idf
                vec[vocab_index[word]] = count * idf[word]
            tfidf_vectors.append(vec)
            
        # Save Python index
        with open(FALLBACK_INDEX_PATH, "wb") as f:
            pickle.dump({
                "vocab": vocab,
                "vocab_index": vocab_index,
                "idf": idf,
                "tfidf_vectors": tfidf_vectors,
                "resolved_df": self.resolved_df,
                "engine_type": "pure_python"
            }, f)
            
        # Save metadata about engine
        with open(os.path.join(RAG_DIR, "rag_config.pkl"), "wb") as f:
            pickle.dump({"engine_type": "pure_python"}, f)
            
        self.engine_type = "pure_python"
        print("Pure-Python Index built and saved successfully!")

    def load_index(self):
        """
        Loads the saved search index based on engine type metadata.
        """
        config_path = os.path.join(RAG_DIR, "rag_config.pkl")
        if not os.path.exists(config_path):
            # Try to build if missing
            if not self.build_index():
                return False
                
        with open(config_path, "rb") as f:
            config = pickle.load(f)
            
        self.engine_type = config.get("engine_type", "pure_python")
        
        if self.engine_type == "faiss":
            try:
                import faiss
                from sentence_transformers import SentenceTransformer
                self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
                self.index = faiss.read_index(FAISS_INDEX_PATH)
                self.resolved_df = pd.read_csv(RESOLVED_META_PATH)
                print("FAISS RAG Index loaded successfully.")
                return True
            except Exception as e:
                print(f"Failed to load FAISS RAG Index: {e}. Trying fallback index...")
                # Try TF-IDF fallback instead
                
        # Load TF-IDF or Pure-Python indices
        if os.path.exists(FALLBACK_INDEX_PATH):
            with open(FALLBACK_INDEX_PATH, "rb") as f:
                data = pickle.load(f)
                
            self.engine_type = data["engine_type"]
            self.resolved_df = data["resolved_df"]
            
            if self.engine_type == "tfidf":
                self.vectorizer = data["vectorizer"]
                self.tfidf_matrix = data["tfidf_matrix"]
                print("TF-IDF RAG Index loaded successfully.")
            elif self.engine_type == "pure_python":
                self.vocab = data["vocab"]
                self.vocab_index = data["vocab_index"]
                self.idf = data["idf"]
                self.tfidf_vectors = data["tfidf_vectors"]
                print("Pure-Python RAG Index loaded successfully.")
            return True
        else:
            print("Index files missing. Rebuilding index...")
            return self.build_index()

    def search(self, query, k=3):
        """
        Searches resolved complaints and returns top k matching records.
        """
        if self.resolved_df is None:
            if not self.load_index():
                return []
                
        if len(self.resolved_df) == 0:
            return []
            
        if self.engine_type == "faiss":
            try:
                import faiss
                # Encode query
                query_vector = self.encoder.encode([query])
                query_vector = np.array(query_vector).astype("float32")
                faiss.normalize_L2(query_vector)
                
                # Search
                distances, indices = self.index.search(query_vector, k)
                
                results = []
                for score, idx in zip(distances[0], indices[0]):
                    if idx < 0 or idx >= len(self.resolved_df):
                        continue
                    row = self.resolved_df.iloc[idx]
                    results.append({
                        "complaint_id": row["complaint_id"],
                        "ward_name": row["ward_name"],
                        "category": row["category"],
                        "description_text": row["description_text"],
                        "resolution_notes": row["resolution_notes"],
                        "score": float(score)
                    })
                return results
            except Exception as e:
                print(f"FAISS search failed: {e}. Trying fallback TF-IDF search...")
                
        if self.engine_type == "tfidf":
            try:
                from sklearn.metrics.pairwise import cosine_similarity
                # Transform query
                query_vec = self.vectorizer.transform([query])
                # Compute similarities
                sims = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
                # Get top indices
                top_indices = np.argsort(sims)[::-1][:k]
                
                results = []
                for idx in top_indices:
                    if sims[idx] <= 0: # Check if there's any similarity
                        if len(results) >= 1: 
                            break
                    row = self.resolved_df.iloc[idx]
                    results.append({
                        "complaint_id": row["complaint_id"],
                        "ward_name": row["ward_name"],
                        "category": row["category"],
                        "description_text": row["description_text"],
                        "resolution_notes": row["resolution_notes"],
                        "score": float(sims[idx])
                    })
                return results
            except Exception as e:
                print(f"TF-IDF search failed: {e}. Using Pure-Python search...")
                
        # Pure-Python Search Fallback
        import re
        def tokenize(text):
            return re.findall(r'\w+', text.lower())
            
        query_tokens = tokenize(query)
        # Compute query vector
        query_vec = {}
        for word in query_tokens:
            if word in self.vocab_index:
                # Basic TF-IDF for query
                query_vec[self.vocab_index[word]] = query_tokens.count(word) * self.idf[word]
                
        # Compute cosine similarity manually
        query_norm = np.sqrt(sum(val ** 2 for val in query_vec.values()))
        if query_norm == 0:
            # Fallback to returning first few items
            results = []
            for i in range(min(k, len(self.resolved_df))):
                row = self.resolved_df.iloc[i]
                results.append({
                    "complaint_id": row["complaint_id"],
                    "ward_name": row["ward_name"],
                    "category": row["category"],
                    "description_text": row["description_text"],
                    "resolution_notes": row["resolution_notes"],
                    "score": 0.0
                })
            return results
            
        scores = []
        for doc_idx, doc_vec in enumerate(self.tfidf_vectors):
            # Dot product
            dot = 0.0
            for idx, val in query_vec.items():
                if idx in doc_vec:
                    dot += val * doc_vec[idx]
            # Doc norm
            doc_norm = np.sqrt(sum(val ** 2 for val in doc_vec.values()))
            
            if doc_norm > 0:
                similarity = dot / (query_norm * doc_norm)
            else:
                similarity = 0.0
            scores.append((similarity, doc_idx))
            
        # Sort and take top k
        scores.sort(reverse=True, key=lambda x: x[0])
        results = []
        for score, idx in scores[:k]:
            row = self.resolved_df.iloc[idx]
            results.append({
                "complaint_id": row["complaint_id"],
                "ward_name": row["ward_name"],
                "category": row["category"],
                "description_text": row["description_text"],
                "resolution_notes": row["resolution_notes"],
                "score": float(score)
            })
        return results

if __name__ == "__main__":
    rag = CivicRAG()
    rag.build_index()
    print("Testing search:")
    res = rag.search("flooded street water pipe burst")
    for r in res:
        print(f"- [{r['category']}] (Score: {r['score']:.3f}) {r['description_text'][:50]}... Resolution: {r['resolution_notes'][:50]}...")

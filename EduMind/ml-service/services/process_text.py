import spacy
import numpy as np
import networkx as nx
import pandas as pd
import nltk
import os
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from PyPDF2 import PdfReader

# 1) Download NLTK data at import time (runs once when the container starts)
nltk.download("stopwords")
STOP_WORDS = set(stopwords.words("english"))
# disable parser & NER if you don't need them for keyword extraction
NLP = spacy.load("en_core_web_sm", disable=["parser", "ner"])

class ProcessText:
    def __init__(self, input_file, output_file):
        """Initialize with PDF file path and output directory."""
        self.input_file = input_file
        self.output_file = output_file

        self.nlp = spacy.load("en_core_web_sm")
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words("english"))
    
    def extract_text_from_pdf(self):
        """Extract text from a PDF file."""
        reader = PdfReader(self.input_file)
        text = "\n\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        return text

    def preprocess_text(self, text):
        """Tokenize, remove stopwords, apply stemming, and filter short words."""
        doc = self.nlp(text.lower())
        tokens = [
            self.stemmer.stem(token.text)
            for token in doc
            if token.is_alpha and token.text not in self.stop_words and len(token.text) > 2
        ]
        return " ".join(tokens)
    
    def extract_keywords_enhanced(self, text, top_n=5, window_size=4):
        """
        Enhanced TextRank keyword extraction:
        - Filters out very short tokens (<3 chars)
        - Uses a sliding co-occurrence window of configurable size
        - Incorporates multi-word noun phrases (from spaCy)
        """
        doc = self.nlp(text)
        
        phrases = set()
        for chunk in doc.noun_chunks:
            lemmas = [
                token.lemma_.lower()
                for token in chunk
                if token.is_alpha and token.lemma_.lower() not in self.stop_words
            ]
            if len(lemmas) > 1:
                phrases.add("_".join(lemmas))
        
        processed = self.preprocess_text(text)
        words = [w for w in processed.split() if len(w) > 2]
        
        if not words:
            return []
        
        graph = nx.Graph()
        graph.add_nodes_from(set(words) | phrases)
        
        for i, w in enumerate(words):
            for j in range(i+1, min(i + window_size, len(words))):
                graph.add_edge(w, words[j])
        
        for phrase in phrases:
            for part in phrase.split("_"):
                if graph.has_node(part):
                    graph.add_edge(phrase, part)
        
        scores = nx.pagerank(graph)
        
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [item[0].replace("_", " ") for item in sorted_items]

    def extract_keywords(self, text, top_n=5):
        """Extract keywords after preprocessing using TextRank algorithm."""
        processed_text = self.preprocess_text(text)
        words = processed_text.split()

        if not words:
            return []

        graph = nx.Graph()
        graph.add_nodes_from(words)

        for i in range(len(words) - 1):
            graph.add_edge(words[i], words[i + 1])

        scores = nx.pagerank(graph)
        sorted_keywords = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [kw[0] for kw in sorted_keywords]

    def chunk_text_by_paragraphs(self, text, min_length=1500):
        """Chunk text based on paragraphs, merging shorter ones."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        merged_paragraphs = []
        temp_paragraph = ""
        
        for p in paragraphs:
            if len(temp_paragraph) + len(p) < min_length:
                temp_paragraph += " " + p
            else:
                if temp_paragraph:
                    merged_paragraphs.append(temp_paragraph.strip())
                temp_paragraph = p
        
        if temp_paragraph:
            merged_paragraphs.append(temp_paragraph.strip())
        
        return merged_paragraphs

    def process_pdf(self):
        """Process the PDF: extract text, chunk, preprocess, rank, and save the best chunks."""

        cleaned_text = self.extract_text_from_pdf()
        chunks = self.chunk_text_by_paragraphs(cleaned_text)
        processed_chunks = [self.preprocess_text(chunk) for chunk in chunks]

        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(processed_chunks)
        tfidf_scores = np.mean(tfidf_matrix.toarray(), axis=1)

        chunk_keywords = [self.extract_keywords_enhanced(chunk) for chunk in chunks]

        ranked_chunks_df = pd.DataFrame({
            "Chunk_Index": range(len(chunks)),
            "Chunk_Text": chunks,
            "Processed_Text": processed_chunks,
            "TFIDF_Score": tfidf_scores,
            "Top_Keywords": [" | ".join(kw) for kw in chunk_keywords]
        })

        ranked_chunks_df = ranked_chunks_df.sort_values(by="TFIDF_Score", ascending=False)

        threshold = ranked_chunks_df["TFIDF_Score"].quantile(0.5)
        top_chunks = ranked_chunks_df[ranked_chunks_df["TFIDF_Score"] >= threshold]
        top_chunks = top_chunks.sort_values(by="Chunk_Index")

        output_file_path = self.output_file
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(top_chunks["Chunk_Text"].tolist()))

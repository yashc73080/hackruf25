#!/usr/bin/env python3
"""
role_matcher_gemini.py
Semantic role→person assignment using Gemini 2.5 Flash Lite embeddings and cosine similarity.
"""

import os
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

# Load your .env.local file to get GEMINI_API_KEYdotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.local"))
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.local"))
load_dotenv(dotenv_path)

import google.generativeai as genai

# --- Configure Gemini client ---
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError(f"❌ GEMINI_API_KEY not found. Checked path: {dotenv_path}")

genai.configure(api_key=api_key)

# --- Example data (replace with your real data) ---
roles = {
    "frontend": "React Next.js Tailwind TypeScript frontend UI development responsive design",
    "backend": "Node.js Express MongoDB REST API server backend database architecture",
    "marketing": "SEO marketing social media content strategy advertising"
}

people = {
    "Nihal": "next javascript frontend react tailwind css ui",
    "Yash": "node.js express mongo backend api server database",
    "Ayush": "seo marketing social media writing strategy",
    "Dev": "python machine learning tensorflow backend data",
    "Ruchi": "knows absolutely nothing"
}

# --- Helper: get embedding from Gemini 2.5 Flash Lite ---
def get_embedding(text: str) -> np.ndarray:
    """
    Uses Gemini 2.5 Flash Lite embedding model to vectorize a string semantically.
    """
    response = genai.embed_content(
        model="models/embedding-001",  # Embedding endpoint works best for similarity
        content=text,
        task_type="semantic_similarity"
    )
    return np.array(response["embedding"], dtype=np.float32)

# --- Compute embeddings for roles and people ---
print("🔹 Generating embeddings using Gemini 2.5 Flash Lite ...")

role_names = list(roles.keys())
person_names = list(people.keys())

role_embeddings = np.vstack([get_embedding(text) for text in roles.values()])
person_embeddings = np.vstack([get_embedding(text) for text in people.values()])

# --- Compute cosine similarity matrix ---
sim_matrix = cosine_similarity(role_embeddings, person_embeddings)

# --- Greedy assignment with readable output ---
assignments = {}
remaining_people = set(range(len(person_names)))

print("\n=== Role Matching Results (Gemini Semantic Embeddings) ===\n")

for i, role in enumerate(role_names):
    sims = sim_matrix[i, :]

    ranked_indices = np.argsort(sims)[::-1]
    ranked_scores = [(person_names[j], sims[j]) for j in ranked_indices]

    best_idx = max(remaining_people, key=lambda j: sims[j]) if remaining_people else None
    if best_idx is not None:
        best_person = person_names[best_idx]
        assignments[role] = best_person
        remaining_people.remove(best_idx)
    else:
        best_person = "_none_"

    print(f"{role}: {best_person}")
    score_str = ", ".join([f"{name}: {score:.2f}" for name, score in ranked_scores])
    print(f"scores = {score_str}\n")

print("✅ Matching complete.")

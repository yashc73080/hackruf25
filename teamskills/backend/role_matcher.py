#!/usr/bin/env python3
"""
role_matcher.py
Simple role→person assignment using cosine similarity on term frequency,
with score breakdowns.
"""

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- Example data (replace with your real data) ---
roles = {
    "frontend": "React Next.js Tailwind TypeScript frontend UI development responsive design",
    "backend": "Node.js Express MongoDB REST API server backend database architecture",
    "marketing": "SEO marketing social media content strategy advertising"
}

people = {
    "Nihal": "next.js javascript frontend react tailwind css ui",
    "Yash": "node.js express mongo backend",
    "Ayush": "seo marketing social media writing strategy",
    "Dev": "python machine learning tensorflow backend data",
    "Ruchi" : "knows absolutely nothing"
}

# --- Vectorize ---
vectorizer = CountVectorizer()
vectorizer.fit(list(roles.values()) + list(people.values()))

role_vecs = vectorizer.transform(list(roles.values()))
person_vecs = vectorizer.transform(list(people.values()))

role_names = list(roles.keys())
person_names = list(people.keys())

# --- Cosine similarity matrix ---
sim_matrix = cosine_similarity(role_vecs, person_vecs)

# --- Greedy assignment with score printing ---
assignments = {}
remaining_people = set(range(len(person_names)))

print("\n=== Role Matching Results ===\n")

for i, role in enumerate(role_names):
    sims = sim_matrix[i, :]

    # Sort people by similarity descending
    ranked_indices = np.argsort(sims)[::-1]
    ranked_scores = [(person_names[j], sims[j]) for j in ranked_indices]

    # Pick best among remaining people
    best_idx = max(remaining_people, key=lambda j: sims[j]) if remaining_people else None
    if best_idx is not None:
        best_person = person_names[best_idx]
        assignments[role] = best_person
        remaining_people.remove(best_idx)
    else:
        best_person = "_none_"

    # --- Print nicely ---
    print(f"{role}: {best_person}")
    score_str = ", ".join([f"{name}: {score:.2f}" for name, score in ranked_scores])
    print(f"scores = {score_str}\n")

from chroma_store import retrieve

queries = [
    "What are the top 5 ways Mason graduates found jobs?",
    "What does ASSIP stand for?",
    "Name three research centers listed in GMU's Research Centers directory.",
]

for query in queries:
    print("=" * 80)
    print(f"QUESTION: {query}")

    results = retrieve(query, top_k=5)

    for i, result in enumerate(results, start=1):
        metadata = result["metadata"]
        text = result["text"].replace("\n", " ")

        print("-" * 80)
        print(f"Rank: {i}")
        print(f"Distance: {result['distance']:.4f}")
        print(f"Source: {metadata.get('source_name')}")
        print(f"Chunk ID: {result['id']}")
        print(f"Text: {text}")

    print("\nAsk yourself: are these chunks actually relevant to the question?\n")
from typing import Iterator, List, Dict, Any

BATCH_SIZE = 200


def export_batches(db, collection_name: str) -> Iterator[List[Dict[str, Any]]]:
    col = db[collection_name]

    cursor = col.find({}).batch_size(BATCH_SIZE)

    batch: List[Dict[str, Any]] = []
    for doc in cursor:
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []

    if batch:
        yield batch

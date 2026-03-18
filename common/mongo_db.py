from common.logger import setup_logger
from pymongo import errors

logger = setup_logger("mongo_db")

def insert_data(data, collection):
    try:
        if data:
            collection.insert_many(data, ordered=False)
            logger.info(f"{collection.name}에 {len(data)}개의 documents 삽입 성공")
        else:
            logger.warning(f"삽입할 데이터가 없습니다: {collection.name}")
    except errors.BulkWriteError as e:
        write_errors = e.details.get("writeErrors", [])
        fail_count = len(write_errors)
        logger.warning(f"{len(data)}개 중 {fail_count}개의 문서 삽입 X (중복 등의 이유)")
    except errors.PyMongoError as e:
        logger.error(f"{collection.name}에 데이터 삽입 실패 : {e}")

def data_transfer(source_collection, target_collection):
    batch_size = 1000

    cursor = source_collection.find(batch_size=batch_size)
    batch = []

    for doc in cursor:
        batch.append(doc)
        if len(batch) == batch_size:
            target_collection.insert_many(batch)
            batch.clear()

    if batch:
        target_collection.insert_many(batch)

    logger.info("데이터 이관 완료")

def ensure_indexes_for_version(collection, filed):
    collection.create_index(filed, unique=True, name=f"uq_{filed}")
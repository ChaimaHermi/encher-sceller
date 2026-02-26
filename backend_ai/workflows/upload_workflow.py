from backend_ai.tools.id_generator import generate_session_id
from backend_ai.tools.image_validator import validate_image
from backend_ai.tools.image_compressor import compress_image
from backend_ai.tools.storage_service import store_file
from backend_ai.tools.hash_service import compute_hash

async def handle_upload(title, description, category, images, documents):

    session_id = generate_session_id()

    stored_images = []
    image_hashes = []

    for img in images:
        content = await img.read()

        # Validation technique
        validate_image(content)

        # Hash pour traçabilité
        file_hash = compute_hash(content)
        image_hashes.append(file_hash)

        # Compression
        compressed = compress_image(content)

        # Stockage
        path = store_file(
            compressed,
            session_id,
            img.filename,
            "images"
        )

        stored_images.append(path)

    stored_documents = []

    if documents:
        for doc in documents:
            content = await doc.read()

            path = store_file(
                content,
                session_id,
                doc.filename,
                "documents"
            )

            stored_documents.append(path)

    return {
        "session_id": session_id,
        "title": title,
        "description": description,
        "category_user": category,
        "images": stored_images,
        "documents": stored_documents,
        "image_hashes": image_hashes,
        "status": "PHASE_1_COMPLETED"
    }
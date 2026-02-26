import os

BASE_PATH = "data/temp_uploads"

def store_file(content, session_id, filename, file_type):

    folder = os.path.join(BASE_PATH, session_id, file_type)
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, filename)

    with open(path, "wb") as f:
        f.write(content)

    return path
from PIL import Image
import io

def compress_image(content: bytes):

    image = Image.open(io.BytesIO(content))
    image.thumbnail((1600, 1600))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)

    return buffer.getvalue()
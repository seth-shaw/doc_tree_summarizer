"""Image classification and document-image extraction helpers."""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from .base import Extracted

IMAGE_SUFFIXES = {'.bmp', '.gif', '.jpeg', '.jpg', '.png', '.tif', '.tiff', '.webp'}


def _vision_images(path: Path, max_pages: int, max_dimension: int) -> list[bytes]:
    """Prepare bounded, normalized images for a vision model."""
    with Image.open(path) as source:
        count = getattr(source, 'n_frames', 1)
        if count <= max_pages:
            indexes = list(range(count))
        else:
            # Sample the beginning, middle, and end of long multi-page scans.
            indexes = (
                sorted({round(i * (count - 1) / (max_pages - 1)) for i in range(max_pages)})
                if max_pages > 1 else [0]
            )
        images = []
        for index in indexes:
            source.seek(index)
            frame = ImageOps.exif_transpose(source).convert('RGB')
            frame.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            output = BytesIO()
            frame.save(output, format='JPEG', quality=85)
            images.append(output.getvalue())
        return images


def extract(path: Path, config: dict, client) -> tuple[Extracted, str]:
    """Classify an image and extract document text when appropriate."""
    image_config = config.get('image', {})
    model = image_config.get('model', 'qwen2.5vl:3b')
    max_pages = int(image_config.get('max_pages', 5))
    if max_pages < 1:
        raise ValueError('extraction.image.max_pages must be at least 1')
    max_dimension = int(image_config.get('max_dimension', 1600))
    if max_dimension < 256:
        raise ValueError('extraction.image.max_dimension must be at least 256')
    image_data = _vision_images(path, max_pages, max_dimension)
    classification = client.characterize_image(model, image_data)
    kind = classification['kind']
    description = classification['description'].strip()
    if kind == 'scanned_document':
        result = extract_document(path, config)
        result.text = f'Image context: {description}\n\n{result.text}'
        result.warnings.insert(
            0,
            'Image classified as a scanned document; OCR/document extraction was applied.',
        )
        return result, kind
    return Extracted(f'Image description: {description}', f'ollama:{model}'), kind


def extract_document(path: Path, config: dict) -> Extracted:
    """Route a scanned image through the configured document extractors."""
    # pylint: disable=import-outside-toplevel
    # Import lazily to avoid a router/image import cycle.
    from .router import extract as route_extract
    return route_extract(path, config)

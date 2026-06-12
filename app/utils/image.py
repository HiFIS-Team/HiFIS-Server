"""이미지 정규화 - 다짐 얼굴 등록용.

iPhone EXIF orientation을 픽셀에 적용해야 다짐 얼굴인식 통과.
다짐 서버 부담↓ + 얼굴인식 충분 → 긴 변 1280px로 다운스케일.
RGB만 받음 → JPEG quality 85로 인코딩.
"""
import logging
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)


class ImageValidationError(ValueError):
    """이미지 형식 불량 (POST 본문 검증 실패용)"""


def ensure_jpeg(image_bytes: bytes, max_side: int = 1280) -> bytes:
    """이미지 바이트를 JPEG로 정규화 (EXIF 적용 + 다운스케일 + RGB).

    실패 시 ImageValidationError - 라우터에서 400으로 변환.
    """
    if not image_bytes:
        raise ImageValidationError("이미지가 비어있습니다.")
    try:
        # verify는 한 번 쓰면 객체 닫힘 → 검증 후 다시 open
        Image.open(BytesIO(image_bytes)).verify()
        img = Image.open(BytesIO(image_bytes))
    except (UnidentifiedImageError, OSError) as e:
        raise ImageValidationError(f"이미지를 읽을 수 없습니다: {e}") from e

    # iPhone EXIF orientation 픽셀 적용 - 다짐 얼굴인식은 EXIF 무시
    img = ImageOps.exif_transpose(img)

    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)

    if img.mode != "RGB":
        img = img.convert("RGB")

    out = BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()

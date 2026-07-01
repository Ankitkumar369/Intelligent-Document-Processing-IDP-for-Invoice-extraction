import cv2
import numpy as np
import fitz
from PIL import Image
from src.core.logger import log


class ImagePreprocessor:

    def pdf_page_to_image(self, filepath, page_no=0, dpi=300):
        doc = fitz.open(filepath)
        page = doc[page_no]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        doc.close()

        img_array = np.frombuffer(img_data, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img

    def preprocess(self, image):
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            deskewed = self._deskew(denoised)
            contrast = cv2.convertScaleAbs(deskewed, alpha=1.3, beta=10)
            sharpened = self._sharpen(contrast)
            _, thresh = cv2.threshold(
                sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            return thresh
        except Exception as e:
            log.error(f"Preprocessing error: {e}")
            return image

    def _deskew(self, image):
        try:
            coords = np.column_stack(np.where(image < 250))
            if len(coords) < 10:
                return image
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            if abs(angle) < 0.5:
                return image

            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                image, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )
            return rotated
        except Exception as e:
            log.warning(f"Deskew failed: {e}")
            return image

    def _sharpen(self, image):
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        return cv2.filter2D(image, -1, kernel)

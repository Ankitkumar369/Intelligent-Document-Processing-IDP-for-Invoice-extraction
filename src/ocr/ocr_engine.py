import pytesseract
from dataclasses import dataclass, field
from typing import List, Dict
from src.core.config import OCR_LANGUAGE, OCR_CONFIDENCE_THRESHOLD
from src.core.logger import log


@dataclass
class OCRWord:
    text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int


@dataclass
class OCRResult:
    full_text: str
    words: List[OCRWord] = field(default_factory=list)
    avg_confidence: float = 0.0
    error: str = ""


class OCREngine:

    def extract(self, image, lang=OCR_LANGUAGE):
        try:
            data = pytesseract.image_to_data(
                image, lang=lang, output_type=pytesseract.Output.DICT
            )

            words = []
            confidences = []
            text_parts = []

            n = len(data["text"])
            for i in range(n):
                txt = data["text"][i].strip()
                conf = float(data["conf"][i])
                if not txt or conf < 0:
                    continue

                words.append(OCRWord(
                    text=txt,
                    confidence=conf,
                    x=data["left"][i],
                    y=data["top"][i],
                    width=data["width"][i],
                    height=data["height"][i],
                ))
                confidences.append(conf)
                text_parts.append(txt)

            full_text = self._reconstruct_text(data)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            log.debug(f"  OCR extracted {len(words)} words | avg_conf={avg_conf:.1f}")

            return OCRResult(
                full_text=full_text,
                words=words,
                avg_confidence=round(avg_conf, 2),
            )

        except Exception as e:
            log.error(f"OCR error: {e}")
            return OCRResult(full_text="", error=str(e))

    def _reconstruct_text(self, data):
        lines = {}
        n = len(data["text"])
        for i in range(n):
            txt = data["text"][i].strip()
            if not txt:
                continue
            line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(line_key, []).append(txt)

        result_lines = []
        for key in sorted(lines.keys()):
            result_lines.append(" ".join(lines[key]))

        return "\n".join(result_lines)

    def is_low_confidence(self, result):
        return result.avg_confidence < OCR_CONFIDENCE_THRESHOLD

from mss import mss
from PIL import Image, ImageOps, ImageEnhance
import pytesseract


def capture_screen():
    with mss() as sct:
        monitor = sct.monitors[0]
        shot = sct.grab(monitor)

        img = Image.frombytes("RGB", shot.size, shot.rgb)

        # Mejorar la imagen para facilitar el reconocimiento.
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        img = ImageEnhance.Contrast(img).enhance(1.5)

        # Ampliar textos pequeños.
        if img.width < 1800:
            factor = 1800 / img.width
            img = img.resize(
                (1800, int(img.height * factor)),
                Image.Resampling.LANCZOS
            )

        text = pytesseract.image_to_string(
            img,
            lang="spa+eng",
            config="--psm 6"
        )

        text = "\n".join(
            line.strip() for line in text.splitlines()
            if line.strip()
        )

        if not text:
            raise RuntimeError(
                "No se detectó texto. Comprueba que haya texto visible."
            )

        return text

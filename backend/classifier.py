"""
classifier.py — CLIP-based portrait vs landscape classifier.
Uses Apple MPS (M1/M2/M3) for GPU acceleration when available.
"""

import warnings
import torch
from PIL import Image
import open_clip
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Supported image extensions
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".tiff", ".tif"}

# ---------------------------------------------------------------------------
# Text prompts — carefully crafted to distinguish intentional portraits
# from landscapes/scenes that may incidentally contain people.
# ---------------------------------------------------------------------------
PORTRAIT_PROMPTS = [
    "a portrait photo of a person",
    "a close-up photo of a person's face",
    "a selfie of a person",
    "a photo focused on a person's face and upper body",
    "a professional headshot",
    "a candid portrait photo of a person",
    "a full body portrait of a person",
    "a group portrait photo of people",
    "a photo where a person is the main subject",
    "a photo of someone posing for the camera",
    "a side profile portrait of a person",
    "a fashion photo of a person",
    "a wedding portrait photo of people",
    "a family portrait photo",
]

LANDSCAPE_PROMPTS = [
    "a landscape photo of nature or scenery",
    "a photo of a city street or building",
    "a scenic photo without people as the main subject",
    "a photo where people are far away or in the background",
    "a photo of food, objects, or places",
    "a travel photo of a location",
    "an architecture photo without a person as the main subject",
    "a wide outdoor scene with scenery as the main subject",
    "a photo of an empty room or interior",
    "a product photo or still life photo",
]

TEMPERATURE = 12.0
PORTRAIT_BIAS = 0.018


class PhotoClassifier:
    def __init__(self):
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.device = None
        self.portrait_features = None
        self.landscape_features = None

    def load(self):
        """Load the CLIP model. Called once at server startup."""
        # Choose best available device
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
            print("✅ Using Apple MPS (GPU acceleration)")
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
            print("✅ Using CUDA GPU")
        else:
            self.device = torch.device("cpu")
            print("⚠️  Using CPU (no GPU detected)")

        print("📥 Loading CLIP model (ViT-B/32)…")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="QuickGELU mismatch")
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained="openai"
            )
        self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
        self.model = self.model.to(self.device)
        self.model.eval()

        # Pre-compute text features for both categories (done once)
        self._encode_text_prompts()
        print("✅ CLIP model ready.")

    def _encode_text_prompts(self):
        """Pre-compute text feature vectors for portrait/landscape prompts."""
        def prompt_features(prompts):
            tokens = self.tokenizer(prompts).to(self.device)
            with torch.no_grad():
                feats = self.model.encode_text(tokens)
                return feats / feats.norm(dim=-1, keepdim=True)

        self.portrait_features = prompt_features(PORTRAIT_PROMPTS)
        self.landscape_features = prompt_features(LANDSCAPE_PROMPTS)

    def _image_variants(self, image: Image.Image) -> list[Image.Image]:
        """Create a few stable crops so small or off-center people are easier to catch."""
        width, height = image.size
        variants = [image]

        short_side = min(width, height)
        if short_side >= 64:
            left = max((width - short_side) // 2, 0)
            top = max((height - short_side) // 2, 0)
            variants.append(image.crop((left, top, left + short_side, top + short_side)))

            upper_top = 0 if height >= width else top
            variants.append(image.crop((left, upper_top, left + short_side, upper_top + short_side)))

        return variants

    def _category_score(self, image_features: torch.Tensor, text_features: torch.Tensor) -> float:
        sims = image_features @ text_features.T
        best_per_crop = sims.max(dim=1).values
        crop_score = best_per_crop.max()
        prompt_score = sims.max(dim=0).values.topk(min(3, sims.shape[1])).values.mean()
        return (0.75 * crop_score + 0.25 * prompt_score).item()

    def classify_image(self, image_path: str) -> dict:
        """
        Classify a single image.

        Returns:
            {
                "label": "portrait" | "landscape",
                "confidence": float (0-1),
                "portrait_score": float,
                "landscape_score": float,
            }
        """
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as e:
            return {"error": str(e), "label": "unknown", "confidence": 0.0}

        image_input = torch.stack([
            self.preprocess(variant) for variant in self._image_variants(image)
        ]).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image_input)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        portrait_sim = self._category_score(image_features, self.portrait_features) + PORTRAIT_BIAS
        landscape_sim = self._category_score(image_features, self.landscape_features)

        # Softmax over the two scores
        scores = torch.tensor([portrait_sim, landscape_sim], device=self.device)
        probs = torch.softmax(scores * TEMPERATURE, dim=0)
        portrait_prob = probs[0].item()
        landscape_prob = probs[1].item()

        if portrait_prob >= landscape_prob:
            label = "portrait"
            confidence = portrait_prob
        else:
            label = "landscape"
            confidence = landscape_prob

        return {
            "label": label,
            "confidence": round(confidence, 4),
            "portrait_score": round(portrait_prob, 4),
            "landscape_score": round(landscape_prob, 4),
        }

    def find_images(self, folder: str) -> list[str]:
        """Recursively find all images in a folder."""
        paths = []
        for root, _, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in IMAGE_EXTENSIONS:
                    paths.append(os.path.join(root, f))
        return sorted(paths)


# Singleton instance
classifier = PhotoClassifier()

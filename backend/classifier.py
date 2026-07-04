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
]

LANDSCAPE_PROMPTS = [
    "a landscape photo of nature or scenery",
    "a photo of a city street or building",
    "a scenic photo without people as the main subject",
    "a photo where people are far away or in the background",
    "a photo of food, objects, or places",
    "a travel photo of a location",
]


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
        """Pre-compute averaged text feature vectors for portrait/landscape."""
        def avg_features(prompts):
            tokens = self.tokenizer(prompts).to(self.device)
            with torch.no_grad():
                feats = self.model.encode_text(tokens)
                feats = feats / feats.norm(dim=-1, keepdim=True)
                return feats.mean(dim=0, keepdim=True)

        self.portrait_features = avg_features(PORTRAIT_PROMPTS)
        self.landscape_features = avg_features(LANDSCAPE_PROMPTS)

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

        image_input = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image_input)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        # Cosine similarity against each category
        portrait_sim = (image_features @ self.portrait_features.T).item()
        landscape_sim = (image_features @ self.landscape_features.T).item()

        # Softmax over the two scores
        scores = torch.tensor([portrait_sim, landscape_sim])
        probs = torch.softmax(scores * 10.0, dim=0)  # temperature scaling
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

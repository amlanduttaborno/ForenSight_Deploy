"""Faithful deployment implementation of ``ForenSight_Final.ipynb``."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch import Tensor, nn
from torchvision.transforms import functional as TF

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


@dataclass
class TrainedResult:
    verdict: str
    preliminary_score: float  # Retained API/database name; value is model probability.
    manipulated_area_pct: float
    regions: list[dict]
    width: int
    height: int
    consistency_score: float
    clip_similarity: float


def letterbox(image: Image.Image, size: int) -> tuple[Image.Image, dict[str, int]]:
    """The notebook's inference-time image preprocessing, without a mask."""
    image = image.convert("RGB")
    width, height = image.size
    scale = min(size / max(width, 1), size / max(height, 1))
    new_width, new_height = max(1, round(width * scale)), max(1, round(height * scale))
    resized = image.resize((new_width, new_height), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), color=(0, 0, 0))
    x0, y0 = (size - new_width) // 2, (size - new_height) // 2
    canvas.paste(resized, (x0, y0))
    return canvas, {"orig_w": width, "orig_h": height, "new_w": new_width, "new_h": new_height, "x0": x0, "y0": y0}


class FixedSRMConv(nn.Module):
    def __init__(self, out_channels: int = 16):
        super().__init__()
        kernels = torch.tensor([
            [[0, 0, 0, 0, 0], [0, -1, 2, -1, 0], [0, 2, -4, 2, 0], [0, -1, 2, -1, 0], [0, 0, 0, 0, 0]],
            [[-1, 2, -2, 2, -1], [2, -6, 8, -6, 2], [-2, 8, -12, 8, -2], [2, -6, 8, -6, 2], [-1, 2, -2, 2, -1]],
            [[0, 0, 0, 0, 0], [0, 0, -1, 0, 0], [0, -1, 4, -1, 0], [0, 0, -1, 0, 0], [0, 0, 0, 0, 0]],
        ], dtype=torch.float32)
        kernels[0] /= 4.0
        kernels[1] /= 12.0
        kernels[2] /= 4.0
        self.register_buffer("weight", kernels[:, None, :, :].repeat(1, 3, 1, 1) / 3.0)
        self.proj = nn.Sequential(nn.Conv2d(3, out_channels, 3, padding=1, bias=False), nn.BatchNorm2d(out_channels), nn.GELU())

    def forward(self, x: Tensor) -> Tensor:
        return self.proj(F.conv2d(x, self.weight, padding=2))


class ForensicEncoder(nn.Module):
    def __init__(self, out_channels: int = 64):
        super().__init__()
        self.srm = FixedSRMConv(16)
        self.net = nn.Sequential(
            nn.Conv2d(16, 32, 3, stride=2, padding=1, bias=False), nn.BatchNorm2d(32), nn.GELU(),
            nn.Conv2d(32, 48, 3, stride=2, padding=1, bias=False), nn.BatchNorm2d(48), nn.GELU(),
            nn.Conv2d(48, out_channels, 3, stride=2, padding=1, bias=False), nn.BatchNorm2d(out_channels), nn.GELU(),
            nn.Conv2d(out_channels, out_channels, 3, stride=2, padding=1, bias=False), nn.BatchNorm2d(out_channels), nn.GELU(),
            nn.Conv2d(out_channels, out_channels, 3, stride=2, padding=1, bias=False), nn.BatchNorm2d(out_channels), nn.GELU(),
        )

    def forward(self, x: Tensor) -> Tensor:
        return self.net(self.srm(x))


class DecoderBlock(nn.Module):
    def __init__(self, in_channels: int, skip_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels + skip_channels, out_channels, 3, padding=1, bias=False), nn.BatchNorm2d(out_channels), nn.GELU(),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False), nn.BatchNorm2d(out_channels), nn.GELU(),
        )

    def forward(self, x: Tensor, skip: Tensor) -> Tensor:
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return self.conv(torch.cat([x, skip], dim=1))


class MultiModalAuthenticityNet(nn.Module):
    """Exact network structure and forward logic from the final notebook."""
    def __init__(self, rgb_backbone: str, clip_name: str):
        super().__init__()
        import timm
        from transformers import CLIPConfig, CLIPModel

        self.rgb_encoder = timm.create_model(rgb_backbone, pretrained=False, features_only=True, out_indices=(0, 1, 2, 3))
        rgb_channels = self.rgb_encoder.feature_info.channels()
        self.forensic_encoder = ForensicEncoder(64)
        # All CLIP parameters are stored in best.pt. CLIPConfig constructs the
        # identical architecture without re-downloading model weights.
        self.clip = CLIPModel(CLIPConfig())
        self.freeze_clip = True
        self.forensic_align = nn.Sequential(nn.Conv2d(64, 64, 1, bias=False), nn.BatchNorm2d(64), nn.GELU())
        self.deep_fuse = nn.Sequential(nn.Conv2d(rgb_channels[-1] + 64, rgb_channels[-1], 1, bias=False), nn.BatchNorm2d(rgb_channels[-1]), nn.GELU())
        self.semantic_gate = nn.Sequential(nn.Linear(1025, rgb_channels[-1]), nn.Sigmoid())
        self.dec3 = DecoderBlock(rgb_channels[-1], rgb_channels[-2], 256)
        self.dec2 = DecoderBlock(256, rgb_channels[-3], 128)
        self.dec1 = DecoderBlock(128, rgb_channels[-4], 64)
        self.seg_head = nn.Sequential(nn.Conv2d(64, 64, 3, padding=1), nn.GELU(), nn.Conv2d(64, 1, 1))
        self.classifier = nn.Sequential(nn.LayerNorm(2881), nn.Linear(2881, 512), nn.GELU(), nn.Dropout(0.30), nn.Linear(512, 1))
        self.consistency_head = nn.Sequential(nn.LayerNorm(2049), nn.Linear(2049, 256), nn.GELU(), nn.Dropout(0.30), nn.Linear(256, 1))

    def _clip_features(self, pixels: Tensor, input_ids: Tensor, attention_mask: Tensor) -> tuple[Tensor, Tensor]:
        with torch.no_grad():
            visual = self.clip.vision_model(pixel_values=pixels)
            text = self.clip.text_model(input_ids=input_ids, attention_mask=attention_mask)
            image_features = self.clip.visual_projection(visual.pooler_output)
            text_features = self.clip.text_projection(text.pooler_output)
        return F.normalize(image_features, dim=-1), F.normalize(text_features, dim=-1)

    def forward(self, image: Tensor, image_raw: Tensor, clip_pixel_values: Tensor, input_ids: Tensor, attention_mask: Tensor, caption_present: Tensor) -> dict[str, Tensor]:
        rgb_feats = self.rgb_encoder(image)
        forensic = self.forensic_align(self.forensic_encoder(image_raw))
        deep = rgb_feats[-1]
        if forensic.shape[-2:] != deep.shape[-2:]:
            forensic = F.interpolate(forensic, size=deep.shape[-2:], mode="bilinear", align_corners=False)
        deep = self.deep_fuse(torch.cat([deep, forensic], dim=1))
        clip_img, clip_txt = self._clip_features(clip_pixel_values, input_ids, attention_mask)
        present = caption_present.float().view(-1, 1)
        text_masked = clip_txt * present
        gate = self.semantic_gate(torch.cat([clip_img, text_masked, present], dim=1)).unsqueeze(-1).unsqueeze(-1)
        deep_gated = deep * (0.5 + gate)
        x = self.dec3(deep_gated, rgb_feats[-2])
        x = self.dec2(x, rgb_feats[-3])
        x = self.dec1(x, rgb_feats[-4])
        segmentation_logits = F.interpolate(self.seg_head(x), size=image.shape[-2:], mode="bilinear", align_corners=False)
        rgb_pool = F.adaptive_avg_pool2d(deep_gated, 1).flatten(1)
        forensic_pool = F.adaptive_avg_pool2d(forensic, 1).flatten(1)
        diff, prod = torch.abs(clip_img - clip_txt) * present, (clip_img * clip_txt) * present
        manipulation_logit = self.classifier(torch.cat([rgb_pool, forensic_pool, clip_img, text_masked, diff, prod, present], dim=1)).squeeze(1)
        consistency_logit = self.consistency_head(torch.cat([clip_img, text_masked, diff, prod, present], dim=1)).squeeze(1)
        return {"manipulation_logit": manipulation_logit, "segmentation_logits": segmentation_logits, "consistency_logit": consistency_logit, "clip_similarity": (clip_img * clip_txt).sum(dim=1) * caption_present.float()}


class TrainedInferenceEngine:
    model_status = "TRAINED MULTIMODAL CHECKPOINT (ForenSight_Final)"

    def __init__(self, checkpoint_path: str, device: str = "auto"):
        self.checkpoint_path = Path(checkpoint_path).resolve()
        if not self.checkpoint_path.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {self.checkpoint_path}")
        self.device = torch.device("cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device))
        checkpoint = torch.load(self.checkpoint_path, map_location="cpu", weights_only=False)
        config = checkpoint["config"]
        self.image_size = int(config["image_size"])
        self.classification_threshold = float(checkpoint["classification_threshold"])
        self.mask_threshold = float(checkpoint["mask_threshold"])
        self.temperature = float(checkpoint.get("temperature", 1.0))
        self.model = MultiModalAuthenticityNet(config["rgb_backbone"], config["clip_name"])
        self.model.load_state_dict(checkpoint["model_state"], strict=True)
        self.model.to(self.device).eval()
        from transformers import CLIPProcessor
        self.processor = CLIPProcessor.from_pretrained(config["clip_name"], local_files_only=True, use_fast=False)

    def _inputs(self, image: Image.Image, caption: str) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor, dict[str, int]]:
        model_image, meta = letterbox(image, self.image_size)
        raw = TF.to_tensor(model_image)
        rgb = TF.normalize(raw, IMAGENET_MEAN, IMAGENET_STD)
        caption = str(caption or "").strip()
        encoded = self.processor(images=model_image, text=[caption], return_tensors="pt", padding="max_length", truncation=True, max_length=77)
        inputs = (rgb.unsqueeze(0), raw.unsqueeze(0), encoded["pixel_values"], encoded["input_ids"], encoded["attention_mask"], torch.tensor([float(bool(caption))]))
        return (*tuple(value.to(self.device) for value in inputs), meta)

    @staticmethod
    def _restore_map(square_map: np.ndarray, meta: dict[str, int]) -> np.ndarray:
        crop = square_map[meta["y0"]:meta["y0"] + meta["new_h"], meta["x0"]:meta["x0"] + meta["new_w"]]
        return cv2.resize(crop, (meta["orig_w"], meta["orig_h"]), interpolation=cv2.INTER_LINEAR)

    @torch.inference_mode()
    def analyze(self, image_bytes: bytes, output_dir: Path, caption: str = "") -> TrainedResult:
        original = Image.open(BytesIO(image_bytes)).convert("RGB")
        inputs = self._inputs(original, caption)
        out = self.model(*inputs[:-1])
        score = float(torch.sigmoid(out["manipulation_logit"].float() / self.temperature)[0].cpu())
        consistency_score = float(torch.sigmoid(out["consistency_logit"].float())[0].cpu())
        clip_similarity = float(out["clip_similarity"].float()[0].cpu())
        square_probability = torch.sigmoid(out["segmentation_logits"])[0, 0].float().cpu().numpy()
        probability = self._restore_map(square_probability, inputs[-1])
        return self._render(original, probability, score, consistency_score, clip_similarity, output_dir)

    def gradcam(self, image_bytes: bytes, output_dir: Path, caption: str = "") -> Path:
        """Create Grad-CAM for the manipulation-classification logit.

        This is deliberately calculated from the saved input and the same
        ``best.pt`` instance, rather than pretending that the segmentation map
        is a Grad-CAM image. Parameter gradients stay disabled to keep the
        explanation request practical on CPU; gradients flow from the RGB input
        to the final RGB encoder feature map.
        """
        original = Image.open(BytesIO(image_bytes)).convert("RGB")
        values = list(self._inputs(original, caption))
        image = values[0].detach().requires_grad_(True)
        values[0] = image
        meta = values[-1]
        captured: dict[str, Tensor] = {}

        def capture(_module, _inputs, outputs):
            activation = outputs[-1]
            activation.retain_grad()
            captured["activation"] = activation

        requires_grad = [parameter.requires_grad for parameter in self.model.parameters()]
        hook = self.model.rgb_encoder.register_forward_hook(capture)
        try:
            for parameter in self.model.parameters():
                parameter.requires_grad_(False)
            self.model.zero_grad(set_to_none=True)
            with torch.enable_grad():
                output = self.model(*values[:-1])
                output["manipulation_logit"][0].backward()
            activation = captured["activation"]
            gradient = activation.grad
            if gradient is None:
                raise RuntimeError("Grad-CAM gradient was unavailable")
            weights = gradient.mean(dim=(2, 3), keepdim=True)
            cam = torch.relu((weights * activation).sum(dim=1, keepdim=True))
            cam = F.interpolate(cam, size=(self.image_size, self.image_size), mode="bilinear", align_corners=False)[0, 0]
            cam = cam.detach().float().cpu().numpy()
        finally:
            hook.remove()
            for parameter, state in zip(self.model.parameters(), requires_grad):
                parameter.requires_grad_(state)
            self.model.zero_grad(set_to_none=True)
        cam -= cam.min()
        cam /= max(float(cam.max()), 1e-8)
        restored = self._restore_map(cam, meta)
        heat = cv2.applyColorMap(np.clip(restored * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        base = np.asarray(original).astype(np.float32)
        heat_rgb = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB).astype(np.float32)
        overlay = cv2.cvtColor(np.clip(0.58 * base + 0.42 * heat_rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "gradcam.jpg"
        cv2.imwrite(str(path), overlay)
        return path

    def _render(self, original: Image.Image, probability: np.ndarray, score: float, consistency_score: float, clip_similarity: float, output_dir: Path) -> TrainedResult:
        width, height = original.size
        binary = (probability >= self.mask_threshold).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        regions = []
        for label in range(1, count):
            x, y, region_width, region_height, area = (int(value) for value in stats[label])
            if area < max(20, int(binary.size * 0.0006)):
                continue
            component = labels == label
            regions.append((x, y, region_width, region_height, area, float(probability[component].mean())))
        regions.sort(key=lambda region: (region[4], region[5]), reverse=True)
        serialised = [{"index": index, "x": x, "y": y, "width": rw, "height": rh, "area_pct": round(100 * area / binary.size, 3), "mean_evidence": round(mean, 4)} for index, (x, y, rw, rh, area, mean) in enumerate(regions[:8], 1)]
        output_dir.mkdir(parents=True, exist_ok=True)
        original.save(output_dir / "original.jpg", quality=95)
        Image.fromarray(binary * 255).save(output_dir / "mask.png")
        np.save(output_dir / "probability_map.npy", probability.astype(np.float32))
        Image.fromarray(np.clip(probability * 255, 0, 255).astype(np.uint8)).save(output_dir / "probability_map.png")
        heat = cv2.applyColorMap(np.clip(probability * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_JET)
        cv2.imwrite(str(output_dir / "heatmap.png"), heat)
        base = np.asarray(original).astype(np.float32)
        heat_rgb = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB).astype(np.float32)
        overlay_rgb = base.copy()
        overlay_rgb[binary.astype(bool)] = 0.55 * base[binary.astype(bool)] + 0.45 * heat_rgb[binary.astype(bool)]
        overlay = cv2.cvtColor(np.clip(overlay_rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
        for region in serialised:
            cv2.rectangle(overlay, (region["x"], region["y"]), (region["x"] + region["width"], region["y"] + region["height"]), (255, 255, 255), 2)
        cv2.imwrite(str(output_dir / "overlay.jpg"), overlay)
        verdict = "LIKELY MANIPULATED" if score >= self.classification_threshold else "LIKELY AUTHENTIC"
        return TrainedResult(verdict, round(score, 4), round(float(binary.mean() * 100), 2), serialised, width, height, round(consistency_score, 4), round(clip_similarity, 4))

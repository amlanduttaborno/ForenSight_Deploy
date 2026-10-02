from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F
import timm
from transformers import CLIPModel

RGB_BACKBONE = "convnext_tiny.fb_in22k_ft_in1k_384"
CLIP_NAME = "openai/clip-vit-base-patch32"


class FixedSRMConv(nn.Module):
    def __init__(self, out_channels=16):
        super().__init__()
        kernels = torch.tensor([
            [[0,0,0,0,0],[0,-1,2,-1,0],[0,2,-4,2,0],[0,-1,2,-1,0],[0,0,0,0,0]],
            [[-1,2,-2,2,-1],[2,-6,8,-6,2],[-2,8,-12,8,-2],[2,-6,8,-6,2],[-1,2,-2,2,-1]],
            [[0,0,0,0,0],[0,0,-1,0,0],[0,-1,4,-1,0],[0,0,-1,0,0],[0,0,0,0,0]],
        ], dtype=torch.float32)
        kernels[0] /= 4.0
        kernels[1] /= 12.0
        kernels[2] /= 4.0
        weight = kernels[:, None, :, :].repeat(1, 3, 1, 1) / 3.0
        self.register_buffer("weight", weight)
        self.proj = nn.Sequential(
            nn.Conv2d(3, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.GELU(),
        )

    def forward(self, x):
        residual = F.conv2d(x, self.weight, padding=2)
        return self.proj(residual)


class ForensicEncoder(nn.Module):
    def __init__(self, out_channels=64):
        super().__init__()
        self.srm = FixedSRMConv(16)
        self.net = nn.Sequential(
            nn.Conv2d(16, 32, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(32), nn.GELU(),
            nn.Conv2d(32, 48, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(48), nn.GELU(),
            nn.Conv2d(48, out_channels, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(out_channels), nn.GELU(),
            nn.Conv2d(out_channels, out_channels, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(out_channels), nn.GELU(),
            nn.Conv2d(out_channels, out_channels, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(out_channels), nn.GELU(),
        )

    def forward(self, x):
        return self.net(self.srm(x))


class DecoderBlock(nn.Module):
    def __init__(self, in_channels, skip_channels, out_channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels + skip_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels), nn.GELU(),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels), nn.GELU(),
        )

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        x = torch.cat([x, skip], dim=1)
        return self.conv(x)


class MultiModalAuthenticityNet(nn.Module):
    def __init__(
        self,
        rgb_backbone=RGB_BACKBONE,
        clip_name=CLIP_NAME,
        forensic_channels=64,
        decoder_channels=(256, 128, 64),
        dropout=0.30,
        pretrained_rgb=True,
        freeze_clip=True,
    ):
        super().__init__()

        self.rgb_encoder = timm.create_model(
            rgb_backbone,
            pretrained=pretrained_rgb,
            features_only=True,
            out_indices=(0, 1, 2, 3),
        )
        rgb_channels = self.rgb_encoder.feature_info.channels()
        if len(rgb_channels) != 4:
            raise RuntimeError(f"Expected 4 RGB stages, got {rgb_channels}")

        self.forensic_encoder = ForensicEncoder(forensic_channels)
        self.clip = CLIPModel.from_pretrained(clip_name)
        self.freeze_clip = freeze_clip

        if freeze_clip:
            for p in self.clip.parameters():
                p.requires_grad = False

        clip_dim = int(self.clip.config.projection_dim)
        deep_ch = rgb_channels[-1]

        self.forensic_align = nn.Sequential(
            nn.Conv2d(forensic_channels, forensic_channels, 1, bias=False),
            nn.BatchNorm2d(forensic_channels), nn.GELU(),
        )
        self.deep_fuse = nn.Sequential(
            nn.Conv2d(deep_ch + forensic_channels, deep_ch, 1, bias=False),
            nn.BatchNorm2d(deep_ch), nn.GELU(),
        )

        self.semantic_gate = nn.Sequential(
            nn.Linear(clip_dim * 2 + 1, deep_ch),
            nn.Sigmoid(),
        )

        d0, d1, d2 = decoder_channels
        self.dec3 = DecoderBlock(deep_ch, rgb_channels[-2], d0)
        self.dec2 = DecoderBlock(d0, rgb_channels[-3], d1)
        self.dec1 = DecoderBlock(d1, rgb_channels[-4], d2)
        self.seg_head = nn.Sequential(
            nn.Conv2d(d2, d2, 3, padding=1),
            nn.GELU(),
            nn.Conv2d(d2, 1, 1),
        )

        cls_in = deep_ch + forensic_channels + clip_dim * 4 + 1
        self.classifier = nn.Sequential(
            nn.LayerNorm(cls_in),
            nn.Linear(cls_in, 512),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(512, 1),
        )

        consistency_in = clip_dim * 4 + 1
        self.consistency_head = nn.Sequential(
            nn.LayerNorm(consistency_in),
            nn.Linear(consistency_in, 256),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(256, 1),
        )

    def _clip_features(self, clip_pixel_values, input_ids, attention_mask):
        ctx = torch.no_grad() if self.freeze_clip else torch.enable_grad()
        with ctx:
            vis = self.clip.vision_model(pixel_values=clip_pixel_values)
            txt = self.clip.text_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )
            img_feat = self.clip.visual_projection(vis.pooler_output)
            txt_feat = self.clip.text_projection(txt.pooler_output)

        return F.normalize(img_feat, dim=-1), F.normalize(txt_feat, dim=-1)

    def forward(
        self, image, image_raw, clip_pixel_values,
        input_ids, attention_mask, caption_present,
        return_features=False
    ):
        rgb_feats = self.rgb_encoder(image)

        forensic = self.forensic_align(self.forensic_encoder(image_raw))
        deep = rgb_feats[-1]
        if forensic.shape[-2:] != deep.shape[-2:]:
            forensic = F.interpolate(
                forensic, size=deep.shape[-2:],
                mode="bilinear", align_corners=False
            )

        deep = self.deep_fuse(torch.cat([deep, forensic], dim=1))

        clip_img, clip_txt = self._clip_features(
            clip_pixel_values, input_ids, attention_mask
        )
        present = caption_present.float().view(-1, 1)
        text_masked = clip_txt * present

        gate_input = torch.cat([clip_img, text_masked, present], dim=1)
        gate = self.semantic_gate(gate_input).unsqueeze(-1).unsqueeze(-1)
        deep_gated = deep * (0.5 + gate)

        x = self.dec3(deep_gated, rgb_feats[-2])
        x = self.dec2(x, rgb_feats[-3])
        x = self.dec1(x, rgb_feats[-4])
        seg_logits = self.seg_head(x)
        seg_logits = F.interpolate(
            seg_logits, size=image.shape[-2:],
            mode="bilinear", align_corners=False
        )

        rgb_pool = F.adaptive_avg_pool2d(deep_gated, 1).flatten(1)
        forensic_pool = F.adaptive_avg_pool2d(forensic, 1).flatten(1)
        diff = torch.abs(clip_img - clip_txt) * present
        prod = (clip_img * clip_txt) * present

        cls_features = torch.cat(
            [rgb_pool, forensic_pool, clip_img, text_masked, diff, prod, present],
            dim=1
        )
        manipulation_logit = self.classifier(cls_features).squeeze(1)

        consistency_features = torch.cat(
            [clip_img, text_masked, diff, prod, present], dim=1
        )
        consistency_logit = self.consistency_head(consistency_features).squeeze(1)
        clip_similarity = (clip_img * clip_txt).sum(dim=1) * caption_present.float()

        result = {
            "manipulation_logit": manipulation_logit,
            "segmentation_logits": seg_logits,
            "consistency_logit": consistency_logit,
            "clip_similarity": clip_similarity,
        }
        if return_features:
            result["cam_feature"] = deep_gated
        return result

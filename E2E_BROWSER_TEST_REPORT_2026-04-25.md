# E2E browser test report — 2026-04-25

Target: `main.py` running via `retouch.service` on `http://localhost:8000`.
Provider tested: Google 官方, model `gemini-3.1-flash-image-preview`.
API key used during testing: user-provided Google key, not persisted in this report.

## Covered flows

### Single-image page `/`

- Page load and automatic API key modal.
- API key modal validation:
  - empty key shows `请输入 Key`.
  - invalid key shows Google `API_KEY_INVALID` error and does not mark key configured.
  - valid key saves successfully and header shows masked Google key plus selected model.
- Text-to-image generation:
  - Prompt: red apple minimalist icon on white background.
  - Result: image generated successfully at `/generated/0524ffbc87e58d3c1473db336a695b69.jpg`.
  - Streaming completed with token/cost metadata.
- Image-edit generation:
  - Uploaded the generated apple image back into the page.
  - Prompt: change apple to blue, preserve white background/minimal icon style.
  - Result: image generated successfully at `/generated/c6e1b71ef06f456c26561cbf9db93155.jpg`.
  - Context panel included both uploaded/generated image turns.
- Text-only follow-up in same chat:
  - Prompt asked to summarize the last image.
  - Result: Chinese text response describing the blue apple icon; no image required.
  - Context updated correctly.
- New chat button:
  - Regenerated `sid`, cleared prompt/result/context UI.
- Dark mode button:
  - Toggles dark class on/off and updates icon.
- Mobile viewport smoke test:
  - 390×844 layout renders; key status is hidden as intended by CSS.

### Batch page `/batch`

- Page load and automatic API key modal.
- Valid Google key save on batch page.
- Multi-file upload using two generated images:
  - thumbnails rendered.
  - estimate text rendered (`约 2 张 × $0.05 ≈ $0.10`).
- Batch processing:
  - Prompt: convert each image to watercolor sticker style.
  - Batch started successfully: `359fe79f068a`.
  - Polling reached `进度 2/2`, total cost `$0.1437`.
  - Both items completed with result URLs:
    - `/generated/47f3e85d121055368e45e2cae02d5d9a.jpg`
    - `/generated/32c9c14f149650b7524a96219b2a0ca7.jpg`
- Compare view:
  - Thumbnail click opens original/result comparison.
  - Metadata displays per-item cost.
- ZIP download:
  - `/batch/download/359fe79f068a` returned `200 application/zip`.
  - ZIP size: `895477` bytes.
- Client-side validation:
  - no prompt: `请输入提示词`.
  - no files: `请上传图片`.

### Backend error-path smoke checks

- `POST /generate` without prompt returns SSE error `请输入描述`.
- `POST /batch/start` without configured API key returns `400 {"error":"请先设置 API Key"}`.

## Observations

- No application JavaScript errors appeared in browser console during tested flows.
- Browser console includes Tailwind CDN production warning from `cdn.tailwindcss.com`; this is not a functional failure.
- Systemd service remained healthy throughout testing.
- No code changes were required from this test pass.

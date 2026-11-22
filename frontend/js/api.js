// Akses API backend. Hanya foto, gambar barcode, berat, dan identitas anggota/bin yang dikirim
// ke /api/verify: ground_truth dan expected_* pada kartu tidak pernah dikirim ke engine keputusan.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError("Cannot reach the server. Make sure the backend is running.", 0);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `Request failed (HTTP ${response.status}).`;
    throw new ApiError(detail, response.status);
  }
  return body;
}

async function fetchBlob(url) {
  const response = await fetch(url);
  if (!response.ok) throw new ApiError(`File ${url} not found.`, response.status);
  return response.blob();
}

export const api = {
  config: () => request("/api/config"),
  items: () => request("/api/items"),
  member: (token) => request(`/api/members/${encodeURIComponent(token)}`),
  bin: (binId) => request(`/api/bins/${encodeURIComponent(binId)}`),

  async verify({ memberToken, binId, weightG, card }) {
    const form = new FormData();
    form.append("member_token", memberToken);
    form.append("bin_id", binId);
    form.append("weight_g", String(weightG));
    form.append("photo", await fetchBlob(card.photo_url), "foto.jpg");
    if (card.barcode_image_url) {
      form.append("barcode_image", await fetchBlob(card.barcode_image_url), "barcode.png");
    }
    return request("/api/verify", { method: "POST", body: form });
  },
};

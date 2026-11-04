// Thin client for the FastAPI backend (project/api.py). Same origin, JSON in and out.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function detail(body, status) {
  if (Array.isArray(body?.detail)) return body.detail.map((d) => d.msg).join("; "); // Pydantic 422
  return body?.detail ?? `The server answered ${status}`;
}

async function request(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "The app's server isn't reachable. Check that it is running.");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detail(data, res.status));
  return data;
}

const query = (params) =>
  new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== "")).toString();

export const api = {
  districts: () => request("/districts"),
  soil: (district, state) => request(`/soil?${query({ district, state })}`),
  recommend: (farm) => request("/recommend", { method: "POST", body: farm }),
  explain: (farm, crop) => request("/explain", { method: "POST", body: { ...farm, crop } }),
  chat: (farmerId, message, farm) => request("/chat", { method: "POST", body: { farmer_id: farmerId, message, farm } }),
  profile: (farmerId) => request(`/profile/${encodeURIComponent(farmerId)}`),
};

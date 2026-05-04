import { ApiError, api } from "@/api/client";
import { API_BASE_URL } from "@/constants";

const okJson = (body: unknown, status = 200) =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  }) as unknown as Response;

const errorResponse = (status: number, message: string) =>
  ({
    ok: false,
    status,
    json: async () => ({ error: message }),
    text: async () => message,
  }) as unknown as Response;

describe("ApiClient", () => {
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  describe("get()", () => {
    it("issues a GET against the base URL with JSON headers", async () => {
      fetchMock.mockResolvedValue(okJson({ id: 1 }));

      const result = await api.get<{ id: number }>("/residences/1");

      expect(result).toEqual({ id: 1 });
      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, init] = fetchMock.mock.calls[0];
      expect(url).toBe(`${API_BASE_URL}/residences/1`);
      expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
    });

    it("appends query params to the URL", async () => {
      fetchMock.mockResolvedValue(okJson([]));

      await api.get("/residences", { city: "Amsterdam", min_price: "500" });

      const [url] = fetchMock.mock.calls[0];
      const parsed = new URL(url as string);
      expect(parsed.searchParams.get("city")).toBe("Amsterdam");
      expect(parsed.searchParams.get("min_price")).toBe("500");
    });

    it("throws ApiError with status and body on non-2xx", async () => {
      fetchMock.mockResolvedValue(errorResponse(404, "not found"));

      await expect(api.get("/missing")).rejects.toMatchObject({
        status: 404,
        message: "not found",
      });
      await expect(api.get("/missing")).rejects.toBeInstanceOf(ApiError);
    });
  });

  describe("post()", () => {
    it("serializes the body and sets method=POST", async () => {
      fetchMock.mockResolvedValue(okJson({ ok: true }, 201));

      await api.post("/filters", { name: "two-bed flats" });

      const [, init] = fetchMock.mock.calls[0];
      expect((init as RequestInit).method).toBe("POST");
      expect((init as RequestInit).body).toBe(JSON.stringify({ name: "two-bed flats" }));
    });

    it("omits the body when no payload is given", async () => {
      fetchMock.mockResolvedValue(okJson({}));

      await api.post("/scrape-runs");

      const [, init] = fetchMock.mock.calls[0];
      expect((init as RequestInit).body).toBeUndefined();
    });
  });

  describe("patch()", () => {
    it("issues a PATCH with serialized body", async () => {
      fetchMock.mockResolvedValue(okJson({ ok: true }));

      await api.patch("/filters/42", { name: "renamed" });

      const [, init] = fetchMock.mock.calls[0];
      expect((init as RequestInit).method).toBe("PATCH");
      expect((init as RequestInit).body).toBe(JSON.stringify({ name: "renamed" }));
    });
  });

  describe("delete()", () => {
    it("returns void on success and throws ApiError on failure", async () => {
      fetchMock.mockResolvedValueOnce(okJson({}, 204));
      await expect(api.delete("/filters/1")).resolves.toBeUndefined();

      fetchMock.mockResolvedValueOnce(errorResponse(403, "forbidden"));
      await expect(api.delete("/filters/2")).rejects.toMatchObject({
        status: 403,
      });
    });
  });
});

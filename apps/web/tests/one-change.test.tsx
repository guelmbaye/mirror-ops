/**
 * L'échappatoire doit être du bon côté de la porte.
 *
 * « Try a piece of your own » ne vivait que sur l'écran Before/After — donc
 * derrière un essayage réussi. Quand le catalogue échoue, la personne est
 * ici, sur l'écran de décision, et n'atteignait jamais le bouton censé la
 * débloquer.
 */

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

const replace = vi.fn();
const push = vi.fn();
const routerStub = { replace, push };
vi.mock("next/navigation", () => ({ useRouter: () => routerStub }));

const getSessionDetail = vi.fn();
const generateVTO = vi.fn();
const uploadGarment = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getSessionDetail: (...a: unknown[]) => getSessionDetail(...a),
    generateVTO: (...a: unknown[]) => generateVTO(...a),
    uploadGarment: (...a: unknown[]) => uploadGarment(...a),
  };
});

vi.mock("@/lib/session", () => ({ readSessionId: () => "s1", stepKey: () => "k" }));

import { ApiError } from "@/lib/api";
import OneChangePage from "@/app/one-change/page";

const DETAIL = {
  session: { id: "s1" },
  analysis: { image_url: "http://api/look.jpg" },
  recommendation: {
    id: "r1",
    action: "CHANGE_JACKET",
    label: "Change the jacket",
    score: 72,
    confidence: "medium",
    what: "Change the jacket.",
    why: "Because it moves the most.",
    how: "Keep the rest.",
    keep: ["top", "shoes"],
    impact: { before: { professional_presence: 58 }, after: { professional_presence: 73 }, dominant_factors: [] },
    requires_vto: true,
    is_addition: false,
    suggested_garment: { id: "jacket_01", name: "Structured Neutral Jacket", category: "jacket" },
    fit: { state: "ALMOST_THERE", score: 74, headline: "Almost there.", detail: "…", weakest_element: "jacket" },
  },
  vto: null,
};

function pickFile() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["x"], "ma-veste.jpg", { type: "image/jpeg" });
  Object.defineProperty(input, "files", { value: [file] });
  return input;
}

describe("écran de décision", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    getSessionDetail.mockReset().mockResolvedValue(DETAIL);
    generateVTO.mockReset().mockResolvedValue({ id: "v1" });
    uploadGarment.mockReset().mockResolvedValue({ id: "asset-1", width: 1024, height: 1300, size_bytes: 1 });
  });

  test("propose d'essayer sa propre pièce sans passer par le catalogue", async () => {
    render(<OneChangePage />);
    await screen.findByText("Change the jacket.");
    expect(screen.getByRole("button", { name: /try a piece of your own/i })).toBeDefined();
  });

  test("reste accessible quand le catalogue échoue", async () => {
    generateVTO.mockRejectedValueOnce(
      new ApiError("VTO_FAILED", "We couldn't build that preview. Try another piece.", true, 502),
    );

    render(<OneChangePage />);
    await screen.findByText("Change the jacket.");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "See the difference" }));
    });

    // L'échec s'affiche...
    await screen.findByText(/couldn't build that preview/i);
    // ...et le bouton de secours est toujours là, sur cet écran.
    expect(screen.getByRole("button", { name: /try a piece of your own/i })).toBeDefined();
  });

  test("téléverse la pièce puis va vers la comparaison", async () => {
    render(<OneChangePage />);
    await screen.findByText("Change the jacket.");

    const input = pickFile();
    await act(async () => {
      fireEvent.change(input);
    });

    await waitFor(() => expect(uploadGarment).toHaveBeenCalledTimes(1));
    const call = generateVTO.mock.calls[0][0] as { garmentAssetId: string };
    expect(call.garmentAssetId).toBe("asset-1");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/compare"));
  });
  test("chaque chemin dit ce qu'il fera", async () => {
    render(<OneChangePage />);
    await screen.findByText("Change the jacket.");

    // Le catalogue : on annonce la pièce, on ne propose pas d'en choisir une.
    expect(screen.getByText(/We'll use our/)).toBeDefined();
    expect(screen.getByText("Structured Neutral Jacket")).toBeDefined();

    // L'import : on dit qu'une photo est attendue.
    expect(screen.getByText(/Photograph the one you're considering/)).toBeDefined();
  });

  test("aucun catalogue n'est proposé à parcourir", async () => {
    render(<OneChangePage />);
    await screen.findByText("Change the jacket.");

    // Règle 3 : une liste de vêtements ferait de Mirror Ops le catalogue
    // qu'il refuse d'être. Une seule pièce est nommée, sans alternative.
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByText(/choose|browse|select a/i)).toBeNull();
  });
});

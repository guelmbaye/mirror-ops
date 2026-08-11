/**
 * Écran 9 du positionnement — « Keep it / Try another ».
 *
 * Règle 3 : ONE CHANGE ne devient jamais une liste de recommandations.
 * « Try another » doit donc échanger la PIÈCE sans jamais toucher à la
 * DÉCISION. Ces tests verrouillent cette frontière côté interface.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";

const replace = vi.fn();
const push = vi.fn();

// Une référence stable, comme celle que renvoie réellement Next.
const routerStub = { replace, push };
vi.mock("next/navigation", () => ({ useRouter: () => routerStub }));

const getSessionDetail = vi.fn();
const listGarments = vi.fn();
const generateVTO = vi.fn();
const uploadGarment = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getSessionDetail: (...args: unknown[]) => getSessionDetail(...args),
    listGarments: (...args: unknown[]) => listGarments(...args),
    generateVTO: (...args: unknown[]) => generateVTO(...args),
    uploadGarment: (...args: unknown[]) => uploadGarment(...args),
  };
});

vi.mock("@/lib/session", () => ({
  readSessionId: () => "session-under-test",
  stepKey: (id: string, step: string) => `${id}:${step}`,
}));

import ComparePage from "@/app/compare/page";

const RECOMMENDATION = {
  id: "r1",
  action: "CHANGE_JACKET",
  what: "Change the jacket.",
  keep: ["top", "bottom", "shoes"],
  is_addition: false,
  suggested_garment: null,
  impact: {
    before: { professional_presence: 58, visual_coherence: 64, confidence_proxy: 55 },
    after: { professional_presence: 74, visual_coherence: 79, confidence_proxy: 71 },
    dominant_factors: ["goal_alignment"],
  },
};

function detail(garmentId: string, resultUrl: string) {
  return {
    session: { id: "session-under-test" },
    recommendation: RECOMMENDATION,
    vto: {
      id: `v-${garmentId}`,
      garment_id: garmentId,
      action: "CHANGE_JACKET",
      simulated: false,
      before_image_url: "http://api/before.jpg",
      result_image_url: resultUrl,
    },
  };
}

describe("écran before / after", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    generateVTO.mockReset().mockResolvedValue({ id: "v-jacket_02" });
    uploadGarment.mockReset().mockResolvedValue({ id: "asset-1", width: 1024, height: 1300, size_bytes: 1 });
    getSessionDetail.mockReset().mockResolvedValue(detail("jacket_01", "http://api/a.jpg"));
    listGarments.mockReset().mockResolvedValue({
      garments: [{ id: "jacket_01" }, { id: "jacket_02" }, { id: "jacket_03" }],
    });
  });

  test("ne consulte le catalogue que dans la catégorie décidée", async () => {
    render(<ComparePage />);
    await screen.findByText("Change the jacket.");
    await waitFor(() => expect(listGarments).toHaveBeenCalledWith("jacket"));
  });

  test("« Try another » échange la pièce sans changer la décision", async () => {
    render(<ComparePage />);
    await screen.findByText("Change the jacket.");

    getSessionDetail.mockResolvedValue(detail("jacket_02", "http://api/b.jpg"));
    const button = await screen.findByRole("button", { name: /try another/i });
    await act(async () => {
      fireEvent.click(button);
    });

    await waitFor(() => expect(generateVTO).toHaveBeenCalledTimes(1));
    const call = generateVTO.mock.calls[0][0] as { garmentAssetId: string };
    expect(call.garmentAssetId).toBe("jacket_02");

    // La décision affichée est toujours la même.
    expect(screen.getByText("Change the jacket.")).toBeDefined();
    expect(replace).not.toHaveBeenCalledWith("/one-change");
  });

  test("masque « Try another » quand la catégorie n'offre aucune alternative", async () => {
    listGarments.mockResolvedValue({ garments: [{ id: "jacket_01" }] });
    render(<ComparePage />);
    await screen.findByText("Change the jacket.");
    await waitFor(() => expect(listGarments).toHaveBeenCalled());

    expect(screen.queryByRole("button", { name: /try another/i })).toBeNull();
  });
  test("on peut essayer sa propre pièce", async () => {
    render(<ComparePage />);
    await screen.findByText("Change the jacket.");

    const button = screen.getByRole("button", { name: /try a piece of your own/i });
    expect(button).toBeDefined();

    // Le champ fichier est masqué : c'est le bouton qui l'ouvre.
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "ma-veste.jpg", { type: "image/jpeg" });
    Object.defineProperty(input, "files", { value: [file] });

    await act(async () => {
      fireEvent.change(input);
    });

    await waitFor(() => expect(uploadGarment).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(generateVTO).toHaveBeenCalledTimes(1));

    // La pièce téléversée est bien celle envoyée au try-on.
    const call = generateVTO.mock.calls[0][0] as { garmentAssetId: string };
    expect(call.garmentAssetId).toBe("asset-1");
    // Et la décision n'a pas bougé.
    expect(screen.getByText("Change the jacket.")).toBeDefined();
  });
});

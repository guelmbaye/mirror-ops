/**
 * L'écran final doit montrer la preuve, pas seulement en parler.
 *
 * Terminer sur du texte prive le parcours de la seule chose qui démontre
 * quelque chose — et laisse l'utilisateur repartir les mains vides.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

const replace = vi.fn();
const push = vi.fn();
const routerStub = { replace, push };
vi.mock("next/navigation", () => ({ useRouter: () => routerStub }));

const getSessionDetail = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getSessionDetail: (...a: unknown[]) => getSessionDetail(...a) };
});
vi.mock("@/lib/session", () => ({
  readSessionId: () => "s1",
  clearSession: vi.fn(),
  stepKey: () => "k",
}));
vi.mock("@/lib/photo", () => ({ clearPhoto: vi.fn() }));

import ReadyPage from "@/app/ready/page";

const RECOMMENDATION = {
  id: "r1",
  action: "CHANGE_JACKET",
  label: "Change the jacket",
  keep: ["top", "shoes"],
  is_addition: false,
};

describe("écran final", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    getSessionDetail.mockReset();
  });

  test("affiche le résultat et permet de l'emporter", async () => {
    getSessionDetail.mockResolvedValue({
      recommendation: RECOMMENDATION,
      vto: { result_image_url: "http://api/after.jpg" },
    });

    render(<ReadyPage />);

    const image = (await screen.findByAltText(/after the change/i)) as HTMLImageElement;
    expect(image.src).toContain("after.jpg");

    const save = screen.getByRole("link", { name: /save this/i });
    // Nouvel onglet : `download` seul est ignoré en cross-origin, et le lien
    // faisait sortir de l'application sans rien enregistrer.
    expect(save.getAttribute("target")).toBe("_blank");
    expect(save.getAttribute("rel")).toContain("noopener");
    expect(save.getAttribute("href")).toContain("after.jpg");
  });

  test("reste lisible quand aucun aperçu n'a été généré", async () => {
    getSessionDetail.mockResolvedValue({
      recommendation: { ...RECOMMENDATION, action: "NO_CHANGE" },
      vto: null,
    });

    render(<ReadyPage />);
    await waitFor(() => expect(getSessionDetail).toHaveBeenCalled());

    // Pas d'image fantôme, pas de bouton qui ne mène nulle part.
    expect(screen.queryByAltText(/after the change/i)).toBeNull();
    expect(screen.queryByRole("link", { name: /save this/i })).toBeNull();
  });
});

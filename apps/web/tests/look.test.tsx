/**
 * L'écran « Your look » envoie une AFFIRMATION au moteur.
 *
 * Incident à l'origine de ces tests : les puces par défaut ne cochaient pas
 * « Jacket », si bien que quelqu'un portant une veste se voyait répondre
 * « Add a jacket ». Une case oubliée ne doit plus pouvoir passer inaperçue.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

const replace = vi.fn();
const push = vi.fn();
const routerStub = { replace, push };
vi.mock("next/navigation", () => ({ useRouter: () => routerStub }));

const setOutfit = vi.fn();

vi.mock("@/lib/photo", () => ({
  getPhoto: () => ({ file: new File(["x"], "look.jpg", { type: "image/jpeg" }), previewUrl: "blob:x" }),
  setPhoto: () => "blob:x",
  clearPhoto: vi.fn(),
  getOutfit: () => null,
  setOutfit: (...args: unknown[]) => setOutfit(...args),
}));

vi.mock("@/lib/session", () => ({ readSessionId: () => "s1", stepKey: () => "k" }));

import LookPage from "@/app/look/page";

describe("écran « your look »", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    setOutfit.mockReset();
  });

  test("écrit en toutes lettres ce qui sera envoyé au moteur", async () => {
    render(<LookPage />);
    expect(await screen.findByText(/Mirror Ops will read this as/)).toBeDefined();
    // Ce qui est déclaré absent doit être nommé, pas seulement omis.
    expect(screen.getByText(/no jacket and accessories/)).toBeDefined();
  });

  test("cocher une pièce la retire de la liste des absentes", async () => {
    render(<LookPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Jacket" }));

    expect(screen.queryByText(/no jacket and accessories/)).toBeNull();
    expect(screen.getByText(/no accessories/)).toBeDefined();
  });

  test("transmet la présence ET l'absence de chaque pièce", async () => {
    render(<LookPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Jacket" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(setOutfit).toHaveBeenCalledTimes(1);
    const outfit = setOutfit.mock.calls[0][0] as Record<string, { present: boolean }>;
    expect(outfit.jacket.present).toBe(true);
    expect(outfit.accessories.present).toBe(false);
    // Les cinq éléments sont déclarés : le moteur ne suppose rien.
    expect(Object.keys(outfit)).toHaveLength(5);
  });
  test("empêche de continuer sans aucune pièce déclarée", async () => {
    render(<LookPage />);
    await screen.findByRole("button", { name: "Continue" });

    // On décoche les trois pièces cochées par défaut.
    for (const label of ["Top", "Bottom", "Shoes"]) {
      fireEvent.click(screen.getByRole("button", { name: label }));
    }

    expect(screen.getByText(/Pick at least one piece/)).toBeDefined();
    expect(screen.getByRole("button", { name: "Continue" })).toHaveProperty("disabled", true);

    // Et rien n'est envoyé au moteur.
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(setOutfit).not.toHaveBeenCalled();
  });
  test("le niveau d'habillement part avec la tenue", async () => {
    render(<LookPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Dressed up" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    const outfit = setOutfit.mock.calls[0][0] as Record<
      string,
      { present: boolean; formality?: number }
    >;
    // Sans cette valeur, mariage et voyage rendraient le même verdict.
    expect(outfit.top.formality).toBeGreaterThan(0.8);
    expect(outfit.shoes.formality).toBeGreaterThan(0.8);
    // Une pièce non portée ne reçoit aucun attribut inventé.
    expect(outfit.jacket.formality).toBeUndefined();
  });

  test("la question reste facultative", async () => {
    render(<LookPage />);
    await screen.findByText(/How dressed up is it/);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    const outfit = setOutfit.mock.calls[0][0] as Record<string, { formality?: number }>;
    // Rien n'est supposé : le moteur décidera avec moins de certitude.
    expect(outfit.top.formality).toBeUndefined();
  });
});

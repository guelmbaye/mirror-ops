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

  test("ne présélectionne aucune pièce", async () => {
    render(<LookPage />);
    await screen.findByRole("button", { name: "Continue" });

    // Des défauts mixtes — haut/bas/chaussures cochés, veste non cochée —
    // apprenaient que les défauts sont corrects, si bien qu'une absence jamais
    // affirmée partait au moteur : « Add a jacket » à quelqu'un qui en porte une.
    for (const label of ["Jacket", "Top", "Bottom", "Shoes", "Accessories"]) {
      expect(screen.getByRole("button", { name: label }).getAttribute("aria-pressed")).toBe(
        "false",
      );
    }
    expect(screen.getByRole("button", { name: "Continue" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  test("écrit en toutes lettres ce qui sera envoyé au moteur", async () => {
    render(<LookPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Top" }));

    expect(screen.getByText(/Mirror Ops will read this as/)).toBeDefined();
    // Ce qui est déclaré absent doit être nommé, pas seulement omis.
    expect(screen.getByText(/no jacket, bottom, shoes and accessories/)).toBeDefined();
  });

  test("prévient explicitement du risque d'une absence non voulue", async () => {
    render(<LookPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Top" }));

    // C'est cette absence qui produit « Add a jacket » : elle doit être
    // impossible à manquer, pas seulement mentionnée.
    expect(screen.getByText(/may tell you to add/)).toBeDefined();

    for (const label of ["Jacket", "Bottom", "Shoes", "Accessories"]) {
      fireEvent.click(screen.getByRole("button", { name: label }));
    }
    expect(screen.queryByText(/may tell you to add/)).toBeNull();
  });

  test("cocher une pièce la retire de la liste des absentes", async () => {
    render(<LookPage />);
    for (const label of ["Top", "Bottom", "Shoes"]) {
      fireEvent.click(await screen.findByRole("button", { name: label }));
    }
    expect(screen.getByText(/no jacket and accessories/)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Jacket" }));
    expect(screen.queryByText(/no jacket and accessories/)).toBeNull();
    expect(screen.getByText(/no accessories/)).toBeDefined();
  });

  test("transmet la présence ET l'absence de chaque pièce", async () => {
    render(<LookPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Jacket" }));
    fireEvent.click(screen.getByRole("button", { name: "Casual" }));
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

    expect(screen.getByText(/Tap each piece you have on/)).toBeDefined();
    expect(screen.getByRole("button", { name: "Continue" })).toHaveProperty("disabled", true);

    // Et rien n'est envoyé au moteur.
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(setOutfit).not.toHaveBeenCalled();
  });
  test("le niveau d'habillement part avec la tenue", async () => {
    render(<LookPage />);
    for (const label of ["Top", "Shoes"]) {
      fireEvent.click(await screen.findByRole("button", { name: label }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Dressed up" }));
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

  test("la question d'habillement est obligatoire", async () => {
    render(<LookPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Top" }));
    await screen.findByText(/How dressed up is it/);

    // Sans elle, tout look est lu comme « moyennement habillé » : un entretien
    // et un voyage rendent alors le même verdict à deux points près, et la
    // thèse du produit devient invisible.
    expect(screen.getByRole("button", { name: "Continue" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByText(/judge the same look differently/)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Casual" }));
    expect(screen.getByRole("button", { name: "Continue" })).toHaveProperty(
      "disabled",
      false,
    );
  });
});

describe("pièce signalée comme plus décontractée", () => {
  test("transmet le CHOIX, sans calculer de niveau", async () => {
    render(<LookPage />);
    for (const label of ["Jacket", "Top", "Shoes"]) {
      fireEvent.click(await screen.findByRole("button", { name: label }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Dressed up" }));

    // La seconde rangée porte la même liste : on vise le bouton signalant.
    const chips = screen.getAllByRole("button", { name: "Jacket" });
    fireEvent.click(chips[chips.length - 1]);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    const outfit = setOutfit.mock.calls[0][0] as Record<string, unknown> & {
      jacket: { formality?: number };
      top: { formality?: number };
    };

    // L'interface déclare, le moteur décide. Convertir « plus décontractée »
    // en un nombre est une règle de décision : la laisser ici imposait de
    // reconstruire le frontend pour la corriger, et rien ne permettait de
    // savoir quelle version tournait.
    expect(outfit.odd_one_out).toBe("jacket");
    expect(outfit.jacket.formality).toBe(outfit.top.formality);
  });

  test("ne signale rien si aucune pièce n'est désignée", async () => {
    setOutfit.mockClear();
    render(<LookPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Top" }));
    fireEvent.click(screen.getByRole("button", { name: "Casual" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    const outfit = setOutfit.mock.calls.at(-1)![0] as Record<string, unknown>;
    expect(outfit.odd_one_out).toBeUndefined();
  });
});

describe("confirmation de ce qui sera envoyé", () => {
  test("la ligne de résumé nomme la pièce signalée", async () => {
    render(<LookPage />);
    for (const label of ["Jacket", "Top", "Shoes"]) {
      fireEvent.click(await screen.findByRole("button", { name: label }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Dressed up" }));

    // Avant signalement : le résumé n'annonce aucune pièce en retrait.
    expect(screen.queryByText(/with the .* more casual than the rest/)).toBeNull();

    const chips = screen.getAllByRole("button", { name: "Jacket" });
    fireEvent.click(chips[chips.length - 1]);

    // Deux essais successifs ont donné « Don't change it » sans qu'on puisse
    // dire si la pièce avait été signalée : rien à l'écran ne le confirmait.
    expect(screen.getByText(/jacket more casual than the rest/)).toBeDefined();
  });

  test("signaler une pièce ne la retire pas de la tenue", async () => {
    render(<LookPage />);
    for (const label of ["Jacket", "Top"]) {
      fireEvent.click(await screen.findByRole("button", { name: label }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Casual" }));

    const chips = screen.getAllByRole("button", { name: "Jacket" });
    fireEvent.click(chips[chips.length - 1]);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    const outfit = setOutfit.mock.calls.at(-1)![0] as Record<string, { present?: boolean }> & {
      odd_one_out?: string;
    };
    expect(outfit.jacket.present).toBe(true);
    expect(outfit.odd_one_out).toBe("jacket");
  });
});

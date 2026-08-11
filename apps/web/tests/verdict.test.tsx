/**
 * Le verdict et le registre ne doivent jamais se contredire.
 *
 * Une version anterieure affichait « Add a jacket » en titre et
 * « Change · Jacket » deux lignes plus bas : le registre codait le verbe en dur.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import type { Recommendation } from "@mirror-ops/types";

import { Verdict } from "@/components/Verdict";

function make(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    id: "r1",
    action: "CHANGE_JACKET",
    label: "Change the jacket",
    score: 72,
    confidence: "medium",
    reason: "highest_expected_impact",
    what: "Change the jacket.",
    why: "Because it moves professional presence the most.",
    how: "Keep the rest of your look exactly as it is.",
    keep: ["top", "shoes"],
    impact: {
      before: { professional_presence: 58 },
      after: { professional_presence: 73 },
      dominant_factors: ["goal_alignment"],
    },
    requires_vto: true,
    is_addition: false,
    suggested_garment: { id: "jacket_01", name: "Structured Neutral Jacket", category: "jacket" },
    fit: {
      state: "ALMOST_THERE",
      score: 74,
      headline: "Almost there.",
      detail: "Your outfit fits the occasion, but the jacket reduces the level of formality.",
      weakest_element: "jacket",
    },
    ...overrides,
  };
}

describe("plaque de verdict", () => {
  test("un remplacement affiche « Change » dans le registre", () => {
    render(<Verdict recommendation={make()} />);
    expect(screen.getByText("Change the jacket.")).toBeDefined();
    expect(screen.getByText("Change")).toBeDefined();
    expect(screen.queryByText("Add")).toBeNull();
  });

  test("un ajout affiche « Add » — jamais « Change »", () => {
    render(
      <Verdict
        recommendation={make({
          is_addition: true,
          label: "Add a jacket",
          what: "Add a jacket.",
        })}
      />,
    );
    expect(screen.getByText("Add a jacket.")).toBeDefined();
    expect(screen.getByText("Add")).toBeDefined();
    expect(screen.queryByText("Change")).toBeNull();
  });

  test("ce qui reste est toujours marqué « Keep »", () => {
    render(<Verdict recommendation={make({ is_addition: true, keep: ["top", "shoes"] })} />);
    expect(screen.getAllByText("Keep")).toHaveLength(2);
  });
  test("le verdict d'adéquation précède le changement", () => {
    render(<Verdict recommendation={make()} />);

    // « FIT THE MOMENT » d'abord, « ONE CHANGE » ensuite : c'est l'ordre du
    // positionnement, et il doit se lire dans le DOM.
    const texts = Array.from(document.querySelectorAll("p, h1")).map((n) => n.textContent);
    const fitIndex = texts.findIndex((t) => t?.includes("Almost there."));
    const changeIndex = texts.findIndex((t) => t?.includes("One change"));
    expect(fitIndex).toBeGreaterThanOrEqual(0);
    expect(fitIndex).toBeLessThan(changeIndex);
  });

  test("l'état FIT annonce que rien ne cloche", () => {
    render(
      <Verdict
        recommendation={make({
          action: "NO_CHANGE",
          label: "Don't change it",
          what: "Don't change it.",
          requires_vto: false,
          fit: {
            state: "FIT",
            score: 89,
            headline: "You're good to go.",
            detail: "Your look already matches what a presentation calls for.",
            weakest_element: null,
          },
        })}
      />,
    );
    expect(screen.getByText("You're good to go.")).toBeDefined();
    expect(screen.getByText("No change needed")).toBeDefined();
  });
});

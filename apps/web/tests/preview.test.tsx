/**
 * L'aperçu doit montrer la photo entière.
 *
 * `object-fit: cover` dans un cadre 3/4 rognait les clichés en pied — la
 * consigne demandait de montrer un maximum de sa tenue, et l'aperçu en cachait
 * une partie. On montrait au photographe autre chose que ce qui serait analysé,
 * et il ne pouvait pas vérifier son cadrage.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, test } from "vitest";

const css = readFileSync(join(process.cwd(), "src/app/globals.css"), "utf-8");

function ruleFor(selector: string): string {
  // Ancré sur un début de ligne : sinon `.capture__img` capture aussi
  // `.capture--filled .capture__img`, et le test lit la mauvaise règle.
  const match = css.match(
    new RegExp(`^${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{([^}]*)\\}`, "m"),
  );
  expect(match, `${selector} not found`).not.toBeNull();
  return match![1];
}

describe("aperçu de la photo", () => {
  test("montre l'image entière, sans la rogner", () => {
    expect(ruleFor(".capture__img")).toContain("object-fit: contain");
    expect(ruleFor(".capture__img")).not.toContain("object-fit: cover");
  });

  test("le cadre s'adapte à la photo une fois prise", () => {
    const filled = ruleFor(".capture--filled");
    expect(filled).toContain("aspect-ratio: auto");
    // Une hauteur maximale évite qu'un cliché très étiré pousse les commandes
    // hors de l'écran.
    expect(filled).toMatch(/max-height:\s*\d+vh/);
  });

  test("la vue caméra garde un cadre fixe et le remplit", () => {
    // Un flux vidéo en direct doit remplir son cadre : le laisser flotter
    // donnerait une fenêtre qui change de forme pendant le cadrage.
    expect(ruleFor(".capture__video")).toContain("object-fit: cover");
    expect(ruleFor(".capture--live")).toContain("aspect-ratio: 3 / 4");
  });
});

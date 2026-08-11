/** Petites conversions d'affichage. Aucune logique produit ici. */

export function pct(value: number): number {
  return Math.round(value * 100);
}

/** L'élément visé par une action, pour le registre "changé / gardé". */
export function actionElement(action: string): string | null {
  const map: Record<string, string> = {
    CHANGE_JACKET: "jacket",
    CHANGE_TOP: "top",
    CHANGE_BOTTOM: "bottom",
    CHANGE_SHOES: "shoes",
    CHANGE_ACCESSORY: "accessories",
    REMOVE_ACCESSORY: "accessories",
    // Le travail couleur se matérialise sur le haut : le registre doit nommer
    // la pièce que l'aperçu remplacera, pas une notion abstraite.
    CHANGE_COLOR: "top",
  };
  return map[action] ?? null;
}

/**
 * La catégorie de vêtement mobilisée par une action.
 *
 * Sert uniquement à proposer une AUTRE exécution du même changement — jamais un
 * autre changement. La décision ne bouge pas ; seule la pièce qui l'incarne
 * peut varier. Le travail de couleur se matérialise sur le haut, comme côté
 * moteur.
 */
export function actionCategory(action: string): string | null {
  const map: Record<string, string> = {
    CHANGE_JACKET: "jacket",
    CHANGE_TOP: "top",
    CHANGE_BOTTOM: "bottom",
    CHANGE_SHOES: "shoes",
    CHANGE_ACCESSORY: "accessories",
    // Le travail couleur se materialise sur le haut.
    CHANGE_COLOR: "top",
  };
  return map[action] ?? null;
}

export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
